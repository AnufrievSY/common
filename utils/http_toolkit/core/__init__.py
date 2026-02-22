import inspect
from functools import wraps
from typing import Any, Callable, Optional

import httpx
from tqdm import tqdm
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
import pickle
import pandas as pd
import redis

from . import types, utils, exceptions


class Wrapper:
    """Базовый класс для обработки запросов к API"""
    response = None

    @staticmethod
    async def _to_coroutine(v):
        return await v if inspect.isawaitable(v) else v

    async def _get(self, k: str):
        if hasattr(self.response, k):
            v = getattr(self.response, k)
            if inspect.isawaitable(v):
                v = await v
                setattr(self.response, k, self._to_coroutine(v))
            return v
        return None

    @property
    async def status(self) -> int:
        response = self.response
        if response is None:
            raise ValueError("Response is None")
        if inspect.isawaitable(response):
            response = await response
        for key in ["status", "status_code"]:
            if hasattr(response, key):
                return int(await self._get(key))
        raise ValueError(f"Статус запроса не найден или не прописан в ответе: {response.__dir__}")

    async def execute(self, func: Callable[..., Any], *args, **kwargs):
        ...

    def wrap(self, func: Callable[..., Any]):

        # 1) Если func async — возвращаем async-обёртку (её надо await'ить)
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def awrapper(*args, **kwargs):
                bound = inspect.signature(func).bind(*args, **kwargs)
                bound.apply_defaults()
                return await self.execute(func, *bound.args, **bound.kwargs)

            return awrapper

        # 2) Если func sync — делаем гибрид:
        #    - в sync-контексте вернём результат (через asyncio.run)
        #    - в async-контексте вернём coroutine, которую надо await'ить
        @wraps(func)
        def swrapper(*args, **kwargs):
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                bound = inspect.signature(func).bind(*args, **kwargs)
                bound.apply_defaults()
                # loop НЕ запущен -> обычный sync-вызов
                return asyncio.run(self.execute(func, *bound.args, **bound.kwargs))
            else:
                bound = inspect.signature(func).bind(*args, **kwargs)
                bound.apply_defaults()
                # loop УЖЕ запущен -> мы не можем блокировать
                # возвращаем корутину (пусть вызывающий await-ит)
                return self.execute(func, *bound.args, **bound.kwargs)

        return swrapper


class Redis:
    """Базовый класс для работы с Redis"""
    scripts: dict[str, Any] = {}

    def __init__(self, prefix: str,
                 host: str = "localhost", port: int = 6379, db: int = 0, password: Optional[str] = None,
                 decode_responses: bool = True
                 ):
        """
        Инициализация Redis
        Args:
            prefix: префикс для ключей в Redis
            host: хост Redis
            port: порт Redis
            db: номер базы данных Redis
            password: пароль для подключения к Redis
            decode_responses: декодирование ответов Redis
        """
        self.prefix = prefix
        self.client = redis.Redis(host=host, port=port, db=db, password=password, decode_responses=decode_responses)

    def register_script(self, name: str, script: str):
        """
        Регистрация скриптов Redis
        Args:
            name: имя скрипта Redis для дальнейшего вызова
            script: LUA скрипт Redis
        """
        self.scripts[name] = self.client.register_script(script)

    def get_df(self) -> pd.DataFrame:
        """Возвращает все данные Redis по текущему prefix в виде DataFrame"""
        cursor = 0
        keys = []
        while True:
            cursor, batch = self.client.scan(cursor=cursor, count=1000)
            keys.extend(batch)
            if cursor == 0:
                break

        rows = []
        for key in tqdm(keys, desc="Redis.get_df", total=len(keys)):
            value = self.client.get(key)

            if value is None:
                continue

            value = pickle.loads(value)

            rows.append({"key": key.decode(), "value": value})

        return pd.DataFrame(rows)

    def delete(self, key: str) -> int:
        """
        Удаляет данные из Redis
        Args:
            key: ключ Redis - допускает передача только фрагмента
        """

        cursor = 0
        deleted = 0
        pattern = f"*{key}*"

        while True:
            cursor, keys = self.client.scan(cursor=cursor, match=pattern, count=1000)
            if keys:
                deleted += self.client.delete(*keys)
            if cursor == 0:
                break
        return deleted

    async def execute_script(self, name: str, keys: list[str], args: list[Any], expected: Any,
                             timeout: int = 60) -> Any:
        """
        Выполнение скрипта Redis
        Args:
            name: имя скрипта Redis
            keys: список ключей Redis
            args: список аргументов Redis
            expected: ожидаемое значение
            timeout: таймаут выполнения скрипта
        """

        if name not in self.scripts:
            raise ValueError(f"Скрипт '{name}' не найден")

        _start_time = time.time()
        while True:
            actual = await asyncio.to_thread(self.scripts[name], keys=keys, args=args)
            if actual == expected:
                return actual
            if time.time() - _start_time >= timeout:
                raise TimeoutError(f"Скрипт '{name}' не вернул ожидаемое значение '{expected}'")
            await asyncio.sleep(0.2)

    async def key(self, **kwargs) -> str:
        """Генерация ключа для Redis"""
        hashkey = await utils.to_hashkey(**kwargs)
        return f"{self.prefix}:{hashkey}"
