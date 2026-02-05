"""
Redis-based global limiters (concurrency / rate) for sync and async functions.

Зачем это нужно
---------------
Обычные лимитеры типа `asyncio.Semaphore` или "rate limiter" в памяти работают
ТОЛЬКО внутри одного процесса Python.

Этот модуль делает лимиты "глобальными":
- между потоками
- между процессами
- между разными скриптами
- даже между разными машинами (если Redis общий)

Как устроено
------------
Используется Redis ZSET:
- member: уникальный `token` (uuid)
- score: время протухания этого токена (expire_at)

Lua-скрипт атомарно:
1) удаляет протухшие элементы (score <= now)
2) проверяет текущий размер множества ZCARD
3) если мест нет — возвращает 0
4) если место есть — добавляет токен и ставит EXPIRE на ключ, возвращает 1

Важно: отличие concurrency_limit vs rate_limit
---------------------------------------------
`concurrency_limit`:
- ограничивает ПАРАЛЛЕЛЬНОЕ выполнение (как semaphore)
- после завершения функции вручную освобождает слот (zrem token)

`rate_limit`:
- ограничивает количество запусков "за окно" (скользящее окно)
- НЕ освобождает слот руками
- слоты исчезают сами, когда истекает их срок (score <= now)

Примеры
-------
Sync:

    limiter = concurrency_limit(limit=5, time_out=30)

    @limiter.sync
    def fetch(*, method, url, headers=None, cookies=None):
        ...

Async:

    limiter = rate_limit(limit=10, window=60)

    @limiter.aio
    async def fetch(*, method, url, headers=None, cookies=None):
        ...

Ключи в Redis
-------------
Ключ строится от:
- method, url, headers, cookies
через `to_hashkey(...)`.

То есть лимит НЕ глобальный вообще на всё, а "на конкретный тип запроса".

Параметр poll
-------------
Если лимит занят - ждем `poll` секунд и проверяем снова.
"""

import asyncio
import datetime
import time
import uuid
from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable

import redis
from ._common import to_hashkey

# NOTE: пока что сделал тут, может быть когда-то придумаю как вынести его в другое место,
# чтобы у пользователей была возможность назначить свой Redis
r = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)

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
_acquire_script = r.register_script(LUA)  # регистрация скрипта в Redis


@dataclass(frozen=True)
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
        release: Нужно ли вручную освобождать слот после выполнения функции.
                 True  -> освобождаем (concurrency limiter)
                 False -> не освобождаем, ждем само-протухание (rate limiter)
        poll: Пауза между попытками занять слот.
    """
    prefix: str
    limit: int
    period: int
    release: bool
    poll: float = 0.2

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
            ok = _acquire_script(
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
                _acquire_script,
                keys=[key],
                args=[datetime.datetime.now().timestamp(), self.period, self.limit, token],
            )
            if ok == 1:
                return
            await asyncio.sleep(self.poll)

    def _release_sync(self, key: str, token: str) -> None:
        """Отчистка слота, для использования в синхронных функциях"""
        if self.release:
            r.zrem(key, token)

    async def _release_async(self, key: str, token: str) -> None:
        """Отчистка слота, для использования в асинхронных функциях"""
        if self.release:
            await asyncio.to_thread(r.zrem, key, token)

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
                  Если процесс упал и не освободил слот — он протухнет сам.
        poll: Задержка между попытками занять слот.
    """

    def __init__(self, limit: int, time_out: int, poll: float = 0.2):
        super().__init__(
            prefix="concurrency_limit",
            limit=int(limit),
            period=int(time_out),
            release=True,
            poll=float(poll),
        )


class rate_limit(_RedisLimiter):
    """
    Глобальный rate limiter "за окно" (скользящее окно по TTL).

    Ограничивает количество запусков в пределах временного окна window.

    Args:
        limit: Максимум запусков в окне.
        window: Размер окна (сек).
        poll: Задержка между попытками.
    """
    def __init__(self, limit: int, window: int, poll: float = 0.2):
        super().__init__(
            prefix="rate_limit",
            limit=int(limit),
            period=int(window),
            release=False,
            poll=float(poll),
        )
