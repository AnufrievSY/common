from typing import Iterable, Final

import subprocess
import logging

from .exceptions import CmdError
from .types import LogLevels

# --- Настройки логгера ---

logging.addLevelName(level=LogLevels.DONE, levelName="DONE")


class ColorHandler(logging.StreamHandler):
    """Потоковый обработчик с раскраской логов по уровням."""

    COLOR_CODES: Final[dict[int, str]] = {
        logging.DEBUG: "\033[90m",      # Gray
        logging.INFO: "\033[97m",       # White
        LogLevels.DONE: "\033[92m",     # Green
        logging.WARNING: "\033[93m",    # Yellow
        logging.ERROR: "\033[91m",      # Red
        logging.CRITICAL: "\033[95m"    # Magenta
    }
    RESET_CODE: Final[str] = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        message = super().format(record)
        color = self.COLOR_CODES.get(record.levelno, "")
        return f"{color}{message}{self.RESET_CODE}" if color else message


def get_logger() -> logging.Logger:
    logger = logging.getLogger(name="PREFLIGHT")
    logger.propagate = False
    logger.setLevel(level=logging.DEBUG)

    formater = logging.Formatter(
        fmt="%(levelname)-9s | %(asctime)s.%(msecs)03d | %(message)s",
        datefmt="%H:%M:%S",
    )

    handler = ColorHandler()
    handler.setFormatter(fmt=formater)
    logger.addHandler(hdlr=handler)

    return logger


# --- Другие операции ---

class SafeSubprocess:
    """Запуск команды. Возвращает CompletedProcess."""
    def __init__(self, cmd: Iterable[str], *, check: bool = True):
        self.cmd = cmd
        self.check = check

    def _execute(self, func, *args, **kwargs):
        try:
            proc = func(*args, **kwargs)
        except FileNotFoundError as e:
            raise CmdError("Команда не найдена", self.cmd) from e

        if self.check and proc.returncode != 0:
            raise CmdError("Команда завершилась с ошибкой", self.cmd, proc)
        return proc

    def run(self) -> subprocess.CompletedProcess:
        return self._execute(
            subprocess.run,
            list(self.cmd),
            capture_output=True,
            text=True,
            shell=False,
        )

    def popen(self) -> subprocess.CompletedProcess:
        self.check = False
        return self._execute(
            subprocess.Popen,
            list(self.cmd),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
