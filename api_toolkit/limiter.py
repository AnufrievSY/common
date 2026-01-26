"""
Redis-based global limiters (concurrency / rate) for sync and async functions.

Назначение
----------
Лимитеры в памяти (например, asyncio.Semaphore) работают только внутри процесса.
Этот модуль реализует глобальные лимиты через Redis:
- между потоками
- между процессами
- между разными скриптами
- между машинами при общем Redis

Алгоритм
--------
Используется Redis ZSET:
- member: уникальный token (uuid)
- score: время протухания токена (expire_at)

Lua-скрипт атомарно:
1) удаляет протухшие элементы (score <= now)
2) проверяет ZCARD
3) если мест нет — возвращает 0
4) если место есть — добавляет токен, ставит EXPIRE, возвращает 1

Типы лимита
-----------
concurrency_limit:
- ограничивает параллельное выполнение
- слот освобождается вручную (zrem token)

rate_limit:
- ограничивает количество запусков за окно
- слот не освобождается вручную
- слоты удаляются сами после истечения TTL

Ключи в Redis
-------------
Ключ формируется из method/url/headers/cookies через to_hashkey(...).
Лимит применяется к конкретному типу запроса.

Параметр poll
-------------
Если лимит занят — ожидание poll секунд и повтор.
"""

import asyncio
import datetime
import time
import uuid
from functools import wraps
from typing import Any, Callable, Optional

import redis
from ._common import to_hashkey

# Lua-скрипт: атомарный Redis-лимиттер.
# Работает как ZSET "слотов", где score = время протухания.
LUA = """
local key = KEYS[1]                 -- Redis ключ ZSET, где хранятся активные слоты (str)
local now = tonumber(ARGV[1])       -- текущее время, в данном модуле это datetime.timestamp (int)
local ttl = tonumber(ARGV[2])       -- TTL слота, на сколько секунд "держать слот" (int)
local limit = tonumber(ARGV[3])     -- максимум занятых слотов (int)
local token = ARGV[4]               -- уникальный токен этого слота (str)

-- Чистка протухших слотов, удаляем все score <= now
redis.call('ZREMRANGEBYSCORE', key, 0, now)

-- Если активных слотов уже >= лимита — отказ (0)
local cnt = redis.call('ZCARD', key)
if cnt >= limit then
  return 0
end

-- Иначе слот занимается:
-- score = now + ttl (время когда слот протухнет)
redis.call('ZADD', key, now + ttl, token)
redis.call('EXPIRE', key, math.ceil(ttl))

return 1
"""
class _RedisLimiter:
    """
    Базовый Redis-лимитер.

    Это внутренний класс (не предполагается, что его будут создавать напрямую),
    но именно он реализует общую механику:

    - формирование ключа
    - атомарный acquire через Lua
    - ожидание (poll loop)
    - release (опционально)

    Внимание:
        Предполагается, что в декорируемой функции будут передаваться kwargs поля,
        от которых зависит формирование ключа (method/url/headers/cookies).

    Args:
        prefix: Префикс ключа Redis (например "concurrency_limit" / "rate_limit").
        limit: Сколько токенов может быть активным одновременно.
        period: TTL токена в секундах (для concurrency) или окно (для rate).
        release: Освобождать слот после выполнения функции.
        poll: Пауза между попытками занять слот.
        redis_client: Redis клиент (опционально).
        host: Хост Redis (если redis_client не передан).
        port: Порт Redis (если redis_client не передан).
        db: Redis DB (если redis_client не передан).
    """

    def __init__(
        self,
        *,
        prefix: str,
        limit: int,
        period: int,
        release: bool,
        poll: float = 0.2,
        redis_client: Optional[redis.Redis] = None,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
    ) -> None:
        self.prefix = prefix
        self.limit = int(limit)
        self.period = int(period)
        self.release = bool(release)
        self.poll = float(poll)
        self._client = redis_client or redis.Redis(
            host=host,
            port=port,
            db=db,
            decode_responses=True,
        )
        self._acquire_script = self._client.register_script(LUA)

    def _key(self, **kwargs) -> str:
        """
        Собирает Redis ключ для лимитера: method, url, headers, cookies
        Returns:
            Полный Redis key: "<prefix>:<hash>"
        """
        base = to_hashkey(
            method=kwargs.get("method"),
            url=kwargs.get("url"),
            headers=kwargs.get("headers"),
            cookies=kwargs.get("cookies"),
        )
        return f"{self.prefix}:{base}"

    def _acquire_sync(self, key: str, token: str) -> None:
        """Проверка слота, для использования в синхронных функциях."""
        while True:
            ok = self._acquire_script(
                keys=[key],
                args=[datetime.datetime.now().timestamp(), self.period, self.limit, token],
            )
            if ok == 1:
                return
            time.sleep(self.poll)

    async def _acquire_async(self, key: str, token: str) -> None:
        """Проверка слота, для использования в асинхронных функциях."""
        while True:
            ok = await asyncio.to_thread(
                self._acquire_script,
                keys=[key],
                args=[datetime.datetime.now().timestamp(), self.period, self.limit, token],
            )
            if ok == 1:
                return
            await asyncio.sleep(self.poll)

    def _release_sync(self, key: str, token: str) -> None:
        """Отчистка слота, для использования в синхронных функциях"""
        if self.release:
            self._client.zrem(key, token)

    async def _release_async(self, key: str, token: str) -> None:
        """Отчистка слота, для использования в асинхронных функциях"""
        if self.release:
            await asyncio.to_thread(self._client.zrem, key, token)

    def sync(self, func: Callable[..., Any]):
        """Декоратор для обычной (sync) функции."""
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = self._key(**kwargs)
            token = uuid.uuid4().hex
            self._acquire_sync(key, token)
            try:
                return func(*args, **kwargs)
            finally:
                self._release_sync(key, token)

        return wrapper

    def aio(self, func: Callable[..., Any]):
        """Декоратор для асинхронной (async) функции."""
        @wraps(func)
        async def wrapper(*args, **kwargs):
            key = self._key(**kwargs)
            token = uuid.uuid4().hex
            await self._acquire_async(key, token)
            try:
                return await func(*args, **kwargs)
            finally:
                await self._release_async(key, token)

        return wrapper


# Публичные “обертки”
class concurrency_limit(_RedisLimiter):
    """
    Глобальный concurrency limiter (как Redis-семафор).

    Ограничивает количество ПАРАЛЛЕЛЬНО выполняемых задач.

    Args:
        limit: Максимум параллельных выполнений.
        time_out: TTL слота в секундах.
        poll: Задержка между попытками занять слот.
        redis_client: Redis клиент (опционально).
        host: Хост Redis (если redis_client не передан).
        port: Порт Redis (если redis_client не передан).
        db: Redis DB (если redis_client не передан).
    """

    def __init__(
        self,
        limit: int,
        time_out: int,
        poll: float = 0.2,
        *,
        redis_client: Optional[redis.Redis] = None,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
    ) -> None:
        super().__init__(
            prefix="concurrency_limit",
            limit=limit,
            period=time_out,
            release=True,
            poll=poll,
            redis_client=redis_client,
            host=host,
            port=port,
            db=db,
        )


class rate_limit(_RedisLimiter):
    """
    Глобальный rate limiter "за окно" (скользящее окно по TTL).

    Ограничивает количество запусков в пределах временного окна window.

    Args:
        limit: Максимум запусков в окне.
        window: Размер окна (сек).
        poll: Задержка между попытками.
        redis_client: Redis клиент (опционально).
        host: Хост Redis (если redis_client не передан).
        port: Порт Redis (если redis_client не передан).
        db: Redis DB (если redis_client не передан).
    """

    def __init__(
        self,
        limit: int,
        window: int,
        poll: float = 0.2,
        *,
        redis_client: Optional[redis.Redis] = None,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
    ) -> None:
        super().__init__(
            prefix="rate_limit",
            limit=limit,
            period=window,
            release=False,
            poll=poll,
            redis_client=redis_client,
            host=host,
            port=port,
            db=db,
        )


__all__ = ["concurrency_limit", "rate_limit"]
