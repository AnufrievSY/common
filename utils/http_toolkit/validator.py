"""
Валидатор ответов (retry / ignore) для sync и async функций

Зачем это нужно
---------------
Этот модуль добавляет к вызову функции "политику":
- какие ответы/исключения игнорировать (и что возвращать вместо них)
- какие ответы/исключения повторять (retry) и с паузой
"""

import asyncio
import inspect
import time
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Awaitable, Callable, Optional, ParamSpec, TypeVar, Union

from .core import Wrapper
from .core.utils import extract_body
from .core.exceptions import InvalidUsageError, TooMuchRetries

P = ParamSpec("P")
R = TypeVar("R")

# return_func может быть sync или async
ReturnFunc = Union[Callable[[Any], Any], Callable[[Any], Awaitable[Any]]]


@dataclass(slots=True)
class _ResponseCondition:
    """
    Базовая настройка условия

    Args:
        statuses: Список HTTP-статусов, на которые реагируем
        exceptions: Список типов исключений, на которые реагируем

    Важно:
        Нужно указать хотя бы одно из: status или exception
    """
    statuses: list[int] = field(default_factory=list)
    exceptions: list[type[BaseException]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.statuses and not self.exceptions:
            raise InvalidUsageError("Нужно указать хотя бы один параметр: status или exception")


@dataclass(slots=True)
class IgnoreCondition(_ResponseCondition):
    """
    Условие "игнорировать"

    Args:
        return_func: Функция, которая будет вызвана, если сработало условие.
    """
    return_func: ReturnFunc = field(default=lambda x: x)


@dataclass(slots=True)
class RetryCondition(_ResponseCondition):
    """
    Условие "повторять запрос"

    Args:
        delay_sec: Пауза между попытками (сек)
        max_count: Максимальное количество повторов (не включая первый вызов)
    """
    delay_sec: float = 0.0
    max_count: int = 1


class Validator(Wrapper):
    """Базовый класс для валидирования результатов запроса"""
    response: Any = None
    exception: Optional[BaseException] = None

    def __init__(self,
                 retry: Optional[RetryCondition] = None,
                 ignore: Optional[IgnoreCondition] = None,
                 ):
        """
        Инициализация валидатора запросов

        Args:
            retry: Условия повтора запроса
            ignore: Условия игнорирования запроса
        """
        if not retry and not ignore:
            raise InvalidUsageError("Нужно указать хотя бы один параметр: retry или ignore")
        self.retry = retry
        self.ignore = ignore

        Wrapper.__init__(self)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    async def _check(self, condition: Union[IgnoreCondition, RetryCondition]) -> bool:
        if condition is None:
            return False

        if self.response is not None:
            if len(condition.statuses) != 0:
                return await self.status in condition.statuses

        if self.exception is not None:
            if len(condition.exceptions) != 0:
                return any(isinstance(self.exception, t) for t in condition.exceptions)

        return False

    async def execute(self, func: Callable[..., Any], *args, **kwargs):
        _c = 0
        while True:
            try:
                _r = func(*args, **kwargs)
                if inspect.isawaitable(_r):
                    _r = await _r
                self.response = _r
                self.exception = None
            except BaseException as exc:
                self.response = None
                self.exception = exc

            if await self._check(self.ignore):
                _r = self.ignore.return_func(self.response)
                if inspect.isawaitable(_r):
                    _r = await _r
                return _r

            if not await self._check(self.retry):
                break

            if _c >= self.retry.max_count:
                raise TooMuchRetries(
                    f"Превышено количество повторов ({self.retry.max_count}). "
                    f"Последний статус={await self.status}, "
                    f"текст={await extract_body(self.response, False)}"
                ) from self.exception

            _c += 1
            await asyncio.sleep(self.retry.delay_sec)

        if self.exception:
            raise self.exception
        return self.response


# Публичные “обертки”
def validate(*,
             retry: Optional[RetryCondition] = None,
             ignore: Optional[IgnoreCondition] = None,
             ):
    """
    Декоратор валидирования ответов на запросы к API сервисов

    Args:
        retry: Условия повтора запроса
        ignore: Условия игнорирования запроса
    """

    def decorator(func: Callable[..., Any]):
        _validator = Validator(retry=retry, ignore=ignore)

        @wraps(func)
        def wrapper(*args, **kwargs):
            return _validator.wrap(func, *args, **kwargs)

        return wrapper

    return decorator
