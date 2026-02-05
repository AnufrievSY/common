from typing import Optional, Any
import time
import asyncio
import redis

from .core.utils import to_hashkey


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
        hashkey = await to_hashkey(**kwargs)
        return f"{self.prefix}:{hashkey}"
import dataclasses
dataclasses.dataclass()