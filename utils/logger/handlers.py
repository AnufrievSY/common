import logging
import telebot
from pathlib import Path
from typing import Final
import sys
import linecache
import traceback


def get_formater(text_format: str, date_format: str) -> logging.Formatter:
    """Создаёт форматтер с заданным шаблоном текста и даты."""
    return logging.Formatter(text_format, date_format)


def get_file_handler(file_path: Path, formater: logging.Formatter,
                     level: int | str = logging.ERROR) -> logging.FileHandler:
    """Создаёт файловый обработчик."""
    handler = logging.FileHandler(file_path, encoding="utf-8")
    handler.setFormatter(formater)
    handler.setLevel(level)
    return handler


class ColorHandler(logging.StreamHandler):
    """
    Потоковый обработчик с раскраской логов по уровням.
    """

    COLOR_CODES: Final[dict[int, str]] = {
        logging.DEBUG: "\033[90m",  # Gray
        logging.INFO: "\033[97m",  # White
        logging.WARNING: "\033[93m",  # Yellow
        logging.ERROR: "\033[91m",  # Red
        logging.CRITICAL: "\033[95m"  # Magenta
    }
    RESET_CODE: Final[str] = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        message = super().format(record)
        color = self.COLOR_CODES.get(record.levelno, "")
        return f"{color}{message}{self.RESET_CODE}" if color else message


def get_stream_handler(formater: logging.Formatter) -> ColorHandler:
    """Создаёт потоковый обработчик (stdout) с цветами."""
    handler = ColorHandler()
    handler.setFormatter(formater)
    return handler


from services.telegram import send_error_traceback
class TelegramHandler(logging.Handler):
    """
    Логгер-хендлер, отправляющий сообщения об ошибках в Telegram.
    """

    def __init__(self, bot: telebot.TeleBot, chat_id: int, message_thread_id: int | None,
                 level: int | str = logging.ERROR):
        super().__init__(level)
        self.bot = bot
        self.chat_id = chat_id
        self.message_thread_id = message_thread_id

    @staticmethod
    def get_custom_traceback() -> tuple[str, str]:
        """
        Собирает сокращённый traceback для отправки в Телеграм.
        """
        _, exc_value, tb = sys.exc_info()
        frames_out: list[str] = []
        while tb:
            frame = tb.tb_frame
            filename = frame.f_code.co_filename
            lineno = tb.tb_lineno
            rel_path = Path(filename)
            dotted_path = ".".join(rel_path.with_suffix("").parts)
            code_line = linecache.getline(filename, lineno).strip()
            frames_out.append(f"► {dotted_path}:{lineno}\n    <code>{code_line}</code>\n")
            tb = tb.tb_next
        return "".join(frames_out), str(exc_value) if exc_value else "Unknown Exception"

    def emit(self, record: logging.LogRecord) -> None:
        traceback_text, exception = self.get_custom_traceback() if record.exc_info else ("", record.getMessage())
        send_error_traceback(
            bot=self.bot, chat_id=self.chat_id, message_thread_id=self.message_thread_id,
            message_text=exception, traceback=traceback_text
        )


def get_bot_handler(formater: logging.Formatter, bot: telebot.TeleBot, chat_id: int,
                    message_thread_id: int | None = None,
                    level: int | str = logging.ERROR) -> TelegramHandler:
    """Создаёт Telegram-обработчик."""
    handler = TelegramHandler(bot=bot, chat_id=chat_id, message_thread_id=message_thread_id, level=level)
    handler.setFormatter(formater)
    handler.setLevel(level)
    return handler

from services.git_hub import Executor as GitHubExecutor
from services.git_hub import GitHubConfig
class GitHubHandler(logging.Handler):
    """
    Хендлер, который при логировании ошибок автоматически создаёт issue на GitHub.
    В описание задачи включается полная трассировка (traceback).
    """

    def __init__(self, token: str, owner: str, assignee_login: list[str], repo: str, project: str,
                 label: str = 'bug', status: str = 'BackLog',
                 level: int | str = logging.ERROR):
        super().__init__(level)

        self.executor = GitHubExecutor(config=GitHubConfig(token=token, owner=owner, repo=repo))
        self.label = label
        self.status = status
        self.project = project
        self.assignee_login = assignee_login

    def emit(self, record: logging.LogRecord):
        # Получаем трассировку, если есть exception
        if record.exc_info:
            traceback_text = "".join(traceback.format_exception(*record.exc_info))
        elif record.stack_info:
            traceback_text = record.stack_info
        else:
            # fallback: просто стек, даже без exc_info
            traceback_text = traceback.format_exc()

        issue_url = self.executor.issues.create(
            title=record.getMessage()[:80],
            body=traceback_text or 'Traceback отсутствует',
            status=self.status,
            label_name=[self.label],
            project=self.project,
            assignee_login=self.assignee_login,
        )
        record.issue_url = issue_url


def get_git_hub_handler(token: str, owner: str, assignee_login: list[str], project: str, repo: str, formater: logging.Formatter,
                        level: int | str = logging.ERROR) -> GitHubHandler:
    """Создаёт GitHub-обработчик."""
    handler = GitHubHandler(token=token, owner=owner, assignee_login=assignee_login, repo=repo, project=project)
    handler.setFormatter(formater)
    handler.setLevel(level)
    return handler
