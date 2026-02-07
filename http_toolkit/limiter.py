"""
Redis-based global limiters

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
"""

import asyncio
import datetime
import uuid
from functools import wraps
from typing import Any, Callable
import inspect

from .core import Redis

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


class _BaseLimiter(Redis):
    """Базовый Redis-лимитер

    Это внутренний класс (не предполагается, что его будут создавать напрямую),
    но именно он реализует общую механику:

    - формирование ключа
    - атомарный acquire через Lua
    - ожидание (poll loop)
    - release (опционально)
    """

    def __init__(self, prefix: str, limit: int, period: int, release: bool):
        """
        Инициализация Redis-лимитера
        Args:
            prefix: Префикс ключа Redis
            limit: Сколько токенов может быть активным одновременно
            period: TTL токена в секундах
            release: Нужно ли вручную освобождать слот после выполнения функции
        """
        super().__init__(prefix=prefix)
        self.register_script(name="acquire_slot", script=LUA)
        self.period = period
        self.limit = limit
        self.release = release

    async def _acquire_slot(self, key: str, token: str) -> None:
        """Проверка доступности слота и занятие"""
        await self.execute_script(
            name="acquire_slot",
            keys=[key],
            args=[datetime.datetime.now().timestamp(), self.period, self.limit, token],
            expected=1
        )

    async def _release_slot(self, key: str, token: str) -> None:
        """Освобождение слота"""
        if self.release:
            await asyncio.to_thread(self.client.zrem, key, token)

    async def wrap(self, func: Callable[..., Any], *args, **kwargs):
        key = await self.key(**kwargs)
        token = uuid.uuid4().hex
        await self._acquire_slot(key, token)
        try:
            if inspect.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            return func(*args, **kwargs)
        finally:
            await self._release_slot(key, token)


# Публичные “обертки”
def concurrency_limit(*, limit: int):
    """
    Глобальный concurrency limiter (как Redis-семафор),
    ограничивает количество параллельно выполняемых задач
    Args:
        limit: Максимум одновременно выполняемых задач
    """
    def decorator(func: Callable[..., Any]):
        _limiter = _BaseLimiter(prefix="concurrency_limit",
                                limit=int(limit),
                                period=1, release=True)

        if inspect.iscoroutinefunction(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                return await _limiter.wrap(func, *args, **kwargs)
        else:
            @wraps(func)
            def wrapper(*args, **kwargs):
                return asyncio.run(_limiter.wrap(func, *args, **kwargs))
        return wrapper
    return decorator

def rate_limit(*, limit: int, period: int):
    """
    Глобальный rate limiter "за окно" (скользящее окно по TTL),
    ограничивает количество запусков в пределах временного окна

    Args:
        limit: Максимум запусков в окне
        period: Размер окна (сек)
    """

    def decorator(func: Callable[..., Any]):
        _limiter = _BaseLimiter(prefix="concurrency_limit",
                               limit=int(limit),
                               period=int(period), release=False)
        @wraps(func)
        def wrapper(*args, **kwargs):
            return _limiter.wrap(func, *args, **kwargs)
        return wrapper
    return decorator