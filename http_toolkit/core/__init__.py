from typing import Any, Callable, Optional
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
import redis

from . import types, utils, exceptions

class Wrapper:
    """Базовый класс для обработки запросов к API"""
    async def execute(self, func: Callable[..., Any], *args, **kwargs): ...

    def wrap(self, func: Callable[..., Any], *args, **kwargs):
        if asyncio.iscoroutinefunction(func):
            return self.execute(func, *args, **kwargs)

        def _run():
            loop = asyncio.new_event_loop()
            try:
                asyncio.set_event_loop(loop)
                return loop.run_until_complete(self.execute(func, *args, **kwargs))
            finally:
                loop.run_until_complete(loop.shutdown_asyncgens())
                loop.close()
        with ThreadPoolExecutor(max_workers=1) as executor:
            features = executor.submit(_run)
            return features.result()


class Redis:
    """Базовый класс для работы с Redis"""
    scripts: dict[str, Any] = {}

    def __init__(self, prefix: str,
                 host: str = "localhost", port: int = 6379, db: int = 0, password: Optional[str] = None):
        """
        Инициализация Redis
        Args:
            prefix: префикс для ключей в Redis
            host: хост Redis
            port: порт Redis
            db: номер базы данных Redis
            password: пароль для подключения к Redis
        """
        self.prefix = prefix
        self.client = redis.Redis(host=host, port=port, db=db, password=password, decode_responses=True)

    def register_script(self, name: str, script: str):
        """
        Регистрация скриптов Redis
        Args:
            name: имя скрипта Redis для дальнейшего вызова
            script: LUA скрипт Redis
        """
        self.scripts[name] = self.client.register_script(script)

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
