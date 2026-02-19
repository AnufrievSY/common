import telebot
import logging
from pathlib import Path
from typing import Literal
from . import formatters, handlers


class Logger:
    _formater: logging.Formatter = handlers.get_formater(
        text_format="%(levelname)-9s| %(asctime)s.%(msecs)03d | %(lineno)-3d %(pathname)s | %(message)s",
        date_format="%d-%m-%Y %H:%M:%S",
    )


    def __init__(self, name: str = '',
                 lvl: Literal['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'] = 'DEBUG',
                 ):
        self.logger = logging.getLogger(name)
        self.logger.propagate = False
        self.logger.setLevel(lvl)

        self._handlers: list[logging.Handler] = []

    def set_formater(self, text_format: str, date_format: str):
        self._formater = handlers.get_formater(text_format=text_format, date_format=date_format)

    def add_stream_handler(self):
        handler = handlers.get_stream_handler(formater=self._formater)
        self.logger.addHandler(handler)

    def add_file_handler(self, file_path: str | Path,
                         lvl: Literal['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'] = 'ERROR'):
        handler = handlers.get_file_handler(
            file_path=Path(file_path),
            formater=self._formater,
            level=lvl,
        )
        self.logger.addHandler(handler)

    def add_git_hub_handler(self, token: str, owner: str, assignee_login: list[str], project: str, repo: str,
                            lvl: Literal['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'] = 'ERROR'):
        handler = handlers.get_git_hub_handler(token=token, owner=owner, assignee_login=assignee_login,
                                               project=project, repo=repo,
                                               formater=self._formater, level=lvl)
        self.logger.addHandler(handler)

    def add_tg_handler(self, bot: telebot.TeleBot, chat_id: int, message_thread_id: int = None,
                       lvl: Literal['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'] = 'ERROR'):
        handler = handlers.get_bot_handler(bot=bot, chat_id=chat_id, message_thread_id=message_thread_id,
                                 formater=self._formater, level=lvl)
        self.logger.addHandler(handler)


def get_logger(name: str, lvl: Literal['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'] = 'DEBUG'):
    return Logger(name=name, lvl=lvl)

