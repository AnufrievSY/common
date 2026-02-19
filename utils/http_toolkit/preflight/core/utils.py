import logging
from typing import Iterable
import subprocess

from utils.logger import Logger
from utils.logger.handlers import get_stream_handler

from .exceptions import CmdError
from .types import LogLevels

def get_logger():
    log = Logger(name='http_toolkit-preflight', lvl="INFO")
    formater = logging.Formatter(
        fmt="%(levelname)-9s | %(asctime)s.%(msecs)03d | %(message)s",
        datefmt="%H:%M:%S",
    )
    handler = get_stream_handler(formater)
    handler.COLOR_CODES.update({LogLevels.DONE: "\033[92m"})  # Green
    log.logger.handlers = [handler]
    logging.addLevelName(level=LogLevels.DONE, levelName="DONE")
    return log.logger

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
