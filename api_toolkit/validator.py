"""
Валидатор ответов (retry / ignore) для sync и async функций.

Назначение
----------
Декоратор добавляет политику обработки ответов:
- игнорирование отдельных ответов/исключений
- повтор попыток с задержкой

Совместимость с лимитерами
--------------------------
Для корректного лимитирования каждая повторная попытка должна проходить
через лимитер. Валидатор ставится снаружи:

    @validator.aio(...)
    @limiter.rate_limit(...).aio
    @limiter.concurrency_limit(...).aio
    async def fetch(...):
        ...

Статус ответа
-------------
Sync: getattr(response, "status_code", 0)
Async: getattr(response, "status", 0)

aiohttp и освобождение соединений
--------------------------------
Если возвращается aiohttp.ClientResponse и требуется повтор,
соединение освобождается (release/close) перед следующей попыткой.
"""

import asyncio
import time
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Awaitable, Callable, Optional, ParamSpec, TypeVar, Union

P = ParamSpec("P")
R = TypeVar("R")

# return_func может быть sync или async
ReturnFunc = Union[Callable[[Any], Any], Callable[[Any], Awaitable[Any]]]

__all__ = [
    "IgnoreCondition",
    "RetryCondition",
    "TooMuchRetry",
    "aio",
    "sync",
]


class TooMuchRetry(RuntimeError):
    """Превышено количество повторных попыток (retry)."""


@dataclass(slots=True)
class _ResponseCondition:
    """
    Базовая настройка условия.

    Args:
        status: Список HTTP-статусов, на которые реагируем.
        exception: Список типов исключений, на которые реагируем.

    Важно:
        Нужно указать хотя бы одно из: status или exception.
    """
    status: list[int] = field(default_factory=list)
    exception: list[type[BaseException]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.status and not self.exception:
            raise ValueError("Нужно указать хотя бы один параметр: status или exception.")


@dataclass(slots=True)
class IgnoreCondition(_ResponseCondition):
    """
    Условие "игнорировать".

    Если сработало — возвращается результат return_func(response).
    По умолчанию return_func возвращает исходный response (identity).
    """
    return_func: ReturnFunc = field(default=lambda x: x)


@dataclass(slots=True)
class RetryCondition(_ResponseCondition):
    """
    Условие "повторять запрос".

    Args:
        delay_sec: Пауза между попытками (сек).
        max_count: Максимальное количество повторов (не включая первый вызов).
    """
    delay_sec: float = 0.0
    max_count: int = 1


def _matches_exception(err: Optional[BaseException], types_: list[type[BaseException]]) -> bool:
    return bool(err) and any(isinstance(err, t) for t in types_)


def _status_sync(response: Any) -> int:
    # requests.Response.status_code
    return int(getattr(response, "status_code", 0) or 0)


def _status_aio(response: Any) -> int:
    # aiohttp.ClientResponse.status
    return int(getattr(response, "status", 0) or 0)


def _text_sync(response: Any) -> str:
    # requests.Response.text (если есть)
    try:
        return str(getattr(response, "text", "") or "")
    except Exception:
        return ""


async def _maybe_await(value: Any) -> Any:
    return await value if asyncio.iscoroutine(value) else value


async def _release_response_if_possible(response: Any) -> None:
    # Освободить сетевой ресурс, если объект похож на aiohttp.ClientResponse.

    if response is None:
        return

    release = getattr(response, "release", None)
    if callable(release):
        res = release()
        if asyncio.iscoroutine(res):
            await res
        return

    close = getattr(response, "close", None)
    if callable(close):
        res = close()
        if asyncio.iscoroutine(res):
            await res


def sync(
    retry: Optional[RetryCondition] = None,
    ignore: Optional[IgnoreCondition] = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Декоратор-валидатор для синхронных функций."""

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            counter = 0  # сколько повторов уже сделано

            while True:
                response: Any = None
                err: Optional[BaseException] = None

                try:
                    response = func(*args, **kwargs)
                except BaseException as e:
                    err = e

                status_code = _status_sync(response)

                # IGNORE
                if ignore:
                    if status_code in ignore.status or _matches_exception(err, ignore.exception):
                        return ignore.return_func(response)  # type: ignore[return-value]

                # RETRY?
                need_retry = False
                if retry:
                    if status_code in retry.status or _matches_exception(err, retry.exception):
                        need_retry = True

                if not need_retry:
                    if err:
                        raise err
                    return response

                if not retry:
                    raise TooMuchRetry("Не задано условие retry, но произошёл запрос на повтор.")

                if counter >= retry.max_count:
                    raise TooMuchRetry(
                        f"Превышено количество повторов ({retry.max_count}). "
                        f"Последний статус={status_code}, текст={_text_sync(response)}"
                    ) from err

                counter += 1
                if retry.delay_sec:
                    time.sleep(retry.delay_sec)

        return wrapper

    return decorator


def aio(
    retry: Optional[RetryCondition] = None,
    ignore: Optional[IgnoreCondition] = None,
) -> Callable[[Callable[P, Awaitable[Any]]], Callable[P, Awaitable[Any]]]:
    """Декоратор-валидатор для асинхронных функций."""

    def decorator(func: Callable[P, Awaitable[Any]]) -> Callable[P, Awaitable[Any]]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
            counter = 0

            while True:
                response: Any = None
                err: Optional[BaseException] = None

                try:
                    response = await func(*args, **kwargs)
                except BaseException as e:
                    err = e

                status = _status_aio(response) if response is not None else 0

                # IGNORE
                if ignore:
                    if (response is not None and status in ignore.status) or _matches_exception(err, ignore.exception):
                        out = ignore.return_func(response)
                        return await _maybe_await(out)

                # RETRY?
                need_retry = False
                if retry:
                    if (response is not None and status in retry.status) or _matches_exception(err, retry.exception):
                        need_retry = True

                if not need_retry:
                    if err:
                        raise err
                    return response

                if not retry:
                    raise TooMuchRetry("Не задано условие retry, но произошёл запрос на повтор.")

                await _release_response_if_possible(response)

                if counter >= retry.max_count:
                    raise TooMuchRetry(
                        f"Превышено количество повторов ({retry.max_count}). Последний статус={status}"
                    ) from err

                counter += 1
                if retry.delay_sec:
                    await asyncio.sleep(retry.delay_sec)

        return wrapper

    return decorator
