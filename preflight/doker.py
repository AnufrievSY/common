import os
import time
from typing import Optional

from preflight.common import get_logger, SafeSubprocess
from preflight.exceptions import CmdError
from preflight.types import LogLevels

log = get_logger()


def is_installed() -> Optional[str]:
    """Ищет Docker Desktop.exe"""
    log.debug("Проверка наличия Docker Desktop.exe")

    PATHS = [
        r"C:\Program Files\Docker\Docker\Docker Desktop.exe",
        r"C:\Program Files (x86)\Docker\Docker\Docker Desktop.exe",
    ]

    for path in PATHS:
        if os.path.exists(path):
            log.log(level=LogLevels.DONE, msg=f'Docker Desktop найден: {path}')
            return path
    log.error("Docker Desktop не найден\n"
              "Ссылка на скачивание: https://www.docker.com/products/docker-desktop/")
    return None


def is_available(ignore_errors: bool = False) -> bool:
    """Проверяет, что docker-cli доступен и демон отвечает"""
    log.debug("Проверка доступности Docker Desktop")

    try:
        SafeSubprocess(["docker", "version"], check=True).run()
        log.log(level=LogLevels.DONE, msg='Docker Desktop запущен')
        return True
    except CmdError:
        if not ignore_errors:
            log.error("Docker Desktop не отвечает", exc_info=True)
        return False


def start_docker(exe: str) -> None:
    """Запускает Docker"""
    log.debug("Запуск Docker")

    SafeSubprocess(cmd=[
        "powershell",
        "-NoProfile",
        "-WindowStyle", "Hidden",
        "-Command",
        f'Start-Process -FilePath "{exe}" -WindowStyle Hidden'
    ]).popen()

    for a in range(60):
        if is_available(ignore_errors=a < 60):
            return
        time.sleep(1)

    raise RuntimeError("Docker запустился, но демон не отвечает")


def ensure() -> None:
    """Гарантирует что Docker доступен"""
    log.info("Проверка доступности Docker")

    if is_available(ignore_errors=True):
        return

    log.info("Docker Desktop не отвечает, пробуем запустить")

    exe_path = is_installed()
    if exe_path:
        start_docker(exe_path)
        return

    raise SystemExit(2)

if __name__ == '__main__':
    ensure()