from dataclasses import dataclass

@dataclass(frozen=True)
class LogLevels:
    DONE: int = 25

@dataclass(frozen=True)
class RedisConfig:
    container_name: str = "redis"
    image: str = "redis:7"
    host: str = "127.0.0.1"
    port: int = 6379

