"""
Зачем это нужно
---------------
Иногда возникает необходимость неоднократно вызывать один и тот же запрос.
Однако сами данные в ответе могут не менять и тогда нет смысла повторять запрос.
Собственно для этого и реализован данный вариант кеширования.

Поведение ttl
-------------
- ttl=None            -> кеш отключён, всегда вызываем функцию
- ttl=float("inf")    -> кеш без срока (без expire)
- ttl=число (сек)     -> кеш на ttl секунд
"""

import httpx
import inspect
import pickle
from functools import wraps
from typing import Callable, Any, Optional

from .core import  Wrapper, Redis

class Cache(Wrapper, Redis):
    """
    Кэширует запрос на определенное время
    Args:
        ttl: Время на которое необходимо кэшировать запрос, допускается:
            - None (по-умолчанию) -> кеш отключён, всегда вызываем функцию
            - float("inf") -> кеш без срока
            - целое число (сек) -> кеш на ttl секунд
    """

    def __init__(self, ttl = None, prefix: str = "cache"):
        """
        Инициализация базового Redis-кэша
        """
        Wrapper.__init__(self)
        Redis.__init__(self, prefix=prefix, decode_responses=False)

        self.ttl = ttl

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    async def execute(self, func: Callable[..., Any], *args, **kwargs) -> httpx.Response:
        key = await self.key(method=args[-1], url=args[-2], **kwargs)

        _cache = self.client.get(key)
        if _cache:
            return httpx.Response(**pickle.loads(_cache))

        answer = func(*args, **kwargs)
        if inspect.isawaitable(answer):
            self.response = await answer
        else:
            self.response = answer

        if await self.status < 300:
            value = {'status_code': await self.status}

            if hasattr(self.response, "json"):
                value['json'] = self.response.json()
            if hasattr(self.response, "body"):
                value['body'] = self.response.body
            if hasattr(self.response, "text"):
                value['text'] = self.response.text
            if hasattr(self.response, "content"):
                value['content'] = self.response.content

            value = pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL)

            if self.ttl == float("inf"):
                self.client.set(name=key, value=value)
            elif int(self.ttl or 0) > 0:
                self.client.setex(name=key, time=self.ttl, value=value)

        return self.response
