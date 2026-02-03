import socket
import time
from preflight.common import get_logger, SafeSubprocess
from preflight.exceptions import CmdError
from preflight.types import LogLevels, RedisConfig

log = get_logger()


def is_image_exists(image: str) -> bool:
    """Проверка наличия image локально."""
    log.debug(f'Проверка наличия {image}')
    try:
        proc = SafeSubprocess(["docker", "images", "-q", image]).run()
        if bool(proc.stdout.strip()):
            log.log(level=LogLevels.DONE, msg=f'image {image} найден')
            return True
        raise Exception(f'image {image} не найден')
    except CmdError:
        log.error(f"image {image} не найден", exc_info=True)
        return False

def is_container_exists(name: str) -> bool:
    try:
        proc = SafeSubprocess(["docker", "ps", "-a", "--format", "{{.Names}}"]).run()
        names = {line.strip() for line in proc.stdout.splitlines() if line.strip()}
        if name in names:
            log.log(level=LogLevels.DONE, msg=f'Контейнер {name} найден')
            return True
        raise Exception(f'Контейнер {name} не найден')
    except CmdError:
        log.error(f"Контейнер {name} не найден", exc_info=True)
        return False


def tcp_ping(host: str, port: int, timeout_sec: float = 0.5) -> bool:
    """Быстрая проверка, что порт вообще слушается"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout_sec)
        try:
            s.connect((host, port))
            return True
        except OSError:
            return False

def is_container_running(name: str) -> bool:
    try:
        proc = SafeSubprocess(["docker", "ps", "--format", "{{.Names}}"]).run()
        names = {line.strip() for line in proc.stdout.splitlines() if line.strip()}
        if name in names:
            log.log(level=LogLevels.DONE, msg=f'Контейнер {name} запущен')
            return True
        log.debug(f'Контейнер {name} не запущен')
        return False
    except CmdError:
        log.error(f"Контейнер {name} не запущен", exc_info=True)
        return False

def is_available(cfg: RedisConfig, ignore_errors: bool = False) -> bool:
    """Проверяет, что Redis живой"""
    if not tcp_ping(cfg.host, cfg.port):
        return False

    if not is_container_running(cfg.container_name):
        return False

    try:
        proc = SafeSubprocess(["docker", "exec", cfg.container_name, "redis-cli", "ping"]).run()
        if proc.returncode == 0 and "PONG" in (proc.stdout or ""):
            log.log(level=LogLevels.DONE, msg=f'Redis запущен')
            return True
        if not ignore_errors:
            raise Exception(f'Redis не отвечает')
    except CmdError:
        if not ignore_errors:
            log.error(f"Redis не отвечает", exc_info=True)
        return False

def start_redis(cfg: RedisConfig) -> None:
    """Поднимает Redis контейнер"""
    log.info(f'Запуск Redis')
    if is_container_exists(cfg.container_name):
        if is_container_running(cfg.container_name):
            return

        SafeSubprocess(["docker", "start", cfg.container_name]).run()
        return

    SafeSubprocess(
        [
            "docker", "run", "-d",
            "--name", cfg.container_name,
            "-p", f"{cfg.port}:6379",
            "--restart", "unless-stopped",
            cfg.image,
        ]
    ).run()
    log.log(level=LogLevels.DONE, msg=f'Redis запущен')


def ensure(cfg: RedisConfig = RedisConfig()) -> None:
    """Гарантирует, что образ Redis доступен"""
    log.info("Проверка доступности Redis")

    if is_available(cfg=cfg, ignore_errors=True):
        return

    log.info("Redis не отвечает, пробуем запустить")
    start_redis(cfg=cfg)

    deadline = time.time() + 10.0
    while time.time() < deadline:
        if is_available(cfg, ignore_errors=True):
            log.log(level=LogLevels.DONE, msg=f"Redis поднят и отвечает: {cfg.host}:{cfg.port}")
            return
        time.sleep(0.3)

    raise RuntimeError("Redis контейнер запущен, но не отвечает (timeout). Проверь логи: docker logs redis")



if __name__ == "__main__":
    print(ensure())
