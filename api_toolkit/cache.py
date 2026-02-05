"""
Redis-based cache decorator for sync and async functions.

Назначение
----------
Модуль предоставляет декоратор, который:
- решает, выполнять запрос или вернуть закешированный результат
- хранит результат в Redis (кеш переживает рестарты)
- удаляет кеш вручную:
  - конкретный запрос
  - по сочетаниям параметров (url/method/params/body/headers/...)
  - весь кеш по префиксу
  - всю Redis DB (осторожно)

Как устроен ключ
----------------
Ключ строится из сегментов для возможности частичной инвалидации:
cache:my_func:m=<...>:u=<...>:h=<...>:c=<...>:p=<...>:b=<...>:a=<...>:k=<...>

Где:
- m/u/h/c/p/b = method/url/headers/cookies/params/body (хэши значений)
- a = args (позиционные аргументы)
- k = прочие kwargs (кроме http-полей)

Поведение ttl
-------------
- ttl=None         -> кеш отключён
- ttl=float("inf") -> кеш без срока
- ttl=число        -> кеш на N секунд

Кеширование ошибок
-----------------
- Исключение -> результат не кешируется
- status_code >= 400 -> результат не кешируется
"""

import asyncio
import time
from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable, Optional, ParamSpec, TypeVar
from ._common import to_hashkey

import redis
import pickle

P = ParamSpec("P")
R = TypeVar("R")

__all__ = ["CacheConfig", "cache"]

_DEFAULT_REDIS_HOST = "localhost"
_DEFAULT_REDIS_PORT = 6379


# -------------------- helpers --------------------

def _is_http_style(kwargs: dict[str, Any]) -> bool:
    # Считаем вызов HTTP-стилем, если есть kwargs:
    return ("url" in kwargs) or ("method" in kwargs)


def _extract_body(kwargs: dict[str, Any]) -> Any:
    # Достаёт тело запроса, берёт первое непустое
    if "json" in kwargs and kwargs.get("json") is not None:
        return {"json": kwargs.get("json")}
    if "data" in kwargs and kwargs.get("data") is not None:
        return {"data": kwargs.get("data")}
    if "body" in kwargs and kwargs.get("body") is not None:
        return {"body": kwargs.get("body")}
    return None


def _cacheable_result(result: Any) -> bool:
    # Определяет, можно ли кешировать результат.
    code = getattr(result, "status_code", None)
    if isinstance(code, int) and code >= 400:
        return False
    return True


# -------------------- core config object --------------------


@dataclass(frozen=True, slots=True)
class CacheConfig:
    """Конфигурация кеша + сами декораторы (sync/aio) + ручное удаление."""

    ttl: Optional[float]
    prefix: str = "cache"
    db: int = 1
    host: str = _DEFAULT_REDIS_HOST
    port: int = _DEFAULT_REDIS_PORT

    retries: int = 2
    retry_delay: float = 0.15

    _client: Optional[redis.Redis] = None  # type: ignore[assignment]

    # ---------- validation ----------

    def __post_init__(self) -> None:
        if self.ttl is not None:
            if self.ttl != float("inf") and self.ttl < 0:
                raise ValueError(
                    "ttl не может быть отрицательным. Используй None, число >= 0 или float('inf')."
                )
        if self.db < 0:
            raise ValueError("db не может быть отрицательным.")
        if self.retries < 0:
            raise ValueError("retries не может быть отрицательным.")
        if self.retry_delay < 0:
            raise ValueError("retry_delay не может быть отрицательным.")

    # ---------- redis client ----------

    def _new_client(self) -> redis.Redis:
        return redis.Redis(
            host=self.host,
            port=self.port,
            db=self.db,
            decode_responses=False,  # bytes
            socket_connect_timeout=2,
            socket_timeout=2,
        )

    def _get_client(self) -> redis.Redis:
        c = object.__getattribute__(self, "_client")
        if c is None:
            c = self._new_client()
            object.__setattr__(self, "_client", c)
        return c

    def _reconnect(self) -> redis.Redis:
        c = self._new_client()
        object.__setattr__(self, "_client", c)
        return c

    def _redis_call(self, fn: Callable[[redis.Redis], Any]) -> Any:
        """
        Выполняет Redis-операцию с reconnect+retry.

        Если Redis умер окончательно — исключение пойдёт наружу.
        wrapper поймает и деградирует в "без кеша".
        """
        last_err: Optional[BaseException] = None
        for _ in range(self.retries + 1):
            try:
                return fn(self._get_client())
            except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError) as e:
                last_err = e
                self._reconnect()
                if self.retry_delay:
                    time.sleep(self.retry_delay)
        raise last_err  # type: ignore[misc]

    # ---------- pack/unpack ----------

    @staticmethod
    def _pack(value: Any) -> bytes:
        """Сериализация значения (pickle)."""
        return pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL)

    @staticmethod
    def _unpack(raw: bytes) -> Any:
        return pickle.loads(raw)

    # ---------- key building ----------

    @staticmethod
    def _func_name(func: Callable[..., Any]) -> str:
        return f"{func.__module__}.{func.__qualname__}"

    def _key_for_call(self, func: Callable[..., Any], args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
        """Формирует ключ Redis для конкретного вызова."""
        fn = self._func_name(func)

        if _is_http_style(kwargs):
            method = kwargs.get("method")
            url = kwargs.get("url")
            headers = kwargs.get("headers")
            cookies = kwargs.get("cookies")
            params = kwargs.get("params")
            body = _extract_body(kwargs)

            other_kwargs = dict(kwargs)
            for k in ("method", "url", "headers", "cookies", "params", "json", "data", "body"):
                other_kwargs.pop(k, None)

            return (
                f"{self.prefix}:{fn}:"
                f"m={to_hashkey(method=method)}:"
                f"u={to_hashkey(url=url)}:"
                f"h={to_hashkey(headers=headers)}:"
                f"c={to_hashkey(cookies=cookies)}:"
                f"p={to_hashkey(params=params)}:"
                f"b={to_hashkey(body=body)}:"
                f"a={to_hashkey(args=())}:"
                f"k={to_hashkey(other_kwargs=other_kwargs)}"
            )

        payload = {"args": args, "kwargs": kwargs}
        return f"{self.prefix}:{fn}:g={to_hashkey(**payload)}"

    # ---------- deletion ----------

    @staticmethod
    def _pattern_seg(name: str, value: Any) -> str:
        """Сегмент для SCAN pattern: если value None -> wildcard, иначе хэш."""
        if value is None:
            return f"{name}=*"
        field_map = {
            "m": "method",
            "u": "url",
            "h": "headers",
            "c": "cookies",
            "p": "params",
            "b": "body",
            "a": "args",
            "k": "other_kwargs",
        }
        hash_key = field_map.get(name, name)
        return f"{name}={to_hashkey(**{hash_key: value})}"

    def _scan_delete(self, pattern: str, limit: int = 100_000) -> int:
        """Удаляет ключи по SCAN pattern."""
        deleted = 0
        cursor = 0
        try:
            while True:
                cursor, keys = self._redis_call(lambda c: c.scan(cursor=cursor, match=pattern, count=1000))
                if keys:
                    deleted += int(self._redis_call(lambda c: c.delete(*keys)))
                    if deleted >= limit:
                        break
                if cursor == 0:
                    break
            return deleted
        except Exception:
            return 0

    def clear_prefix(self, *, limit: int = 1_000_000) -> int:
        """Удалить весь кеш под текущим prefix."""
        return self._scan_delete(f"{self.prefix}:*", limit=limit)

    def flushdb(self) -> bool:
        """Очистить ВСЮ Redis DB (db=self.db)."""
        try:
            self._redis_call(lambda c: c.flushdb())
            return True
        except Exception:
            return False

    def invalidate(
        self,
        func: Optional[Callable[..., Any]] = None,
        *,
        method: Any = None,
        url: Any = None,
        headers: Any = None,
        cookies: Any = None,
        params: Any = None,
        body: Any = None,
        args: Any = None,
        other_kwargs: Any = None,
        limit: int = 100_000,
    ) -> int:
        """Удалить кеш по любым сочетаниям параметров."""
        fn = "*" if func is None else self._func_name(func)

        if any(x is not None for x in (method, url, headers, cookies, params, body, args, other_kwargs)):
            m = self._pattern_seg("m", method)
            u = self._pattern_seg("u", url)
            h = self._pattern_seg("h", headers)
            c = self._pattern_seg("c", cookies)
            p = self._pattern_seg("p", params)
            b = self._pattern_seg("b", body)
            a = self._pattern_seg("a", args)
            k = self._pattern_seg("k", other_kwargs)

            pattern = f"{self.prefix}:{fn}:{m}:{u}:{h}:{c}:{p}:{b}:{a}:{k}"
            return self._scan_delete(pattern, limit=limit)

        return self._scan_delete(f"{self.prefix}:{fn}:*", limit=limit)

    # ---------- decorators ----------

    def sync(self, func: Callable[P, R]) -> Callable[P, R]:
        """
        Sync-декоратор кеша.

        1) ttl=None -> кеш выключен
        2) GET -> если нашли -> вернуть
        3) иначе выполнить функцию
        4) если результат кешируемый -> SETEX/SET
        """

        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            if self.ttl is None:
                return func(*args, **kwargs)

            key = self._key_for_call(func, tuple(args), dict(kwargs))

            # 1) read cache
            try:
                raw = self._redis_call(lambda c: c.get(key))
                if raw is not None:
                    return self._unpack(raw)
            except Exception:
                # Redis недоступен -> просто выполняем запрос без кеша
                return func(*args, **kwargs)

            # 2) compute
            result = func(*args, **kwargs)

            # 3) decide cache
            if not _cacheable_result(result):
                return result

            # 4) save
            try:
                payload = self._pack(result)

                if self.ttl == float("inf"):
                    self._redis_call(lambda c: c.set(key, payload))
                    return result

                ttl_sec = int(self.ttl or 0)
                if ttl_sec <= 0:
                    # ttl=0 -> по смыслу "не хранить"
                    return result

                self._redis_call(lambda c: c.setex(key, ttl_sec, payload))
            except Exception:
                pass

            return result

        return wrapper

    def aio(self, func: Callable[P, Any]) -> Callable[P, Any]:
        """
        Async-декоратор кеша.

        Redis клиент синхронный, поэтому операции Redis выполняются через asyncio.to_thread().
        """

        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
            if self.ttl is None:
                return await func(*args, **kwargs)

            key = self._key_for_call(func, tuple(args), dict(kwargs))

            # 1) read cache
            try:
                raw = await asyncio.to_thread(self._redis_call, lambda c: c.get(key))
                if raw is not None:
                    return self._unpack(raw)
            except Exception:
                return await func(*args, **kwargs)

            # 2) compute
            result = await func(*args, **kwargs)

            # 3) decide cache
            if not _cacheable_result(result):
                return result

            # 4) save
            try:
                payload = self._pack(result)

                if self.ttl == float("inf"):
                    await asyncio.to_thread(self._redis_call, lambda c: c.set(key, payload))
                    return result

                ttl_sec = int(self.ttl or 0)
                if ttl_sec <= 0:
                    return result

                await asyncio.to_thread(self._redis_call, lambda c: c.setex(key, ttl_sec, payload))
            except Exception:
                pass

            return result

        return wrapper


# -------------------- public factory --------------------


def cache(
    ttl: Optional[float] = None,
    *,
    prefix: str = "cache",
    db: int = 1,
    host: str = _DEFAULT_REDIS_HOST,
    port: int = _DEFAULT_REDIS_PORT,
    retries: int = 2,
    retry_delay: float = 0.15,
) -> CacheConfig:
    """
    Фабрика конфигурации Redis-кеша.

    Использование:
        from decorators import cache

        @cache(ttl=60).sync
        def func(...):
            ...

    Args:
        ttl: Время хранения в секундах.
             None -> кеш выключен
             float("inf") -> кеш без срока
             число -> кеш на N секунд
        prefix: Префикс ключей Redis.
        db: Redis DB (по умолчанию 1, чтобы не мешаться с лимитером).
        host: Хост Redis.
        port: Порт Redis.
        retries: Количество попыток переподключения к Redis.
        retry_delay: Пауза между попытками переподключения.

    Returns:
        CacheConfig: объект с методами .sync / .aio и методами управления кешем.
    """
    return CacheConfig(
        ttl=ttl,
        prefix=prefix,
        db=db,
        host=host,
        port=port,
        retries=retries,
        retry_delay=retry_delay,
    )
