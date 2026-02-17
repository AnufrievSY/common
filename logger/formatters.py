import os
from pathlib import Path
import logging


class PathFilter(logging.Filter):
    """
    Фильтр, который удаляет абсолютный root-путь из начала пути файла в логах.
    """

    def __init__(self, root_path: str | Path):
        super().__init__()
        self.root_path = os.path.normpath(str(root_path))

    def filter(self, record: logging.LogRecord) -> bool:
        record.pathname = record.pathname.replace(self.root_path, "..")
        return True

SIMPLE_FORMATER: dict[str, str] = {
    "text_format": "%(levelname)-9s| %(asctime)s.%(msecs)03d | %(lineno)-3d %(module)s | %(message)s",
    "date_format": "%H:%M:%S",
}
DETAILED_FORMATER: dict[str, str] = {
    "text_format": "%(levelname)-9s| %(asctime)s.%(msecs)03d | %(lineno)-3d %(pathname)s | %(message)s",
    "date_format": "%d-%m-%Y %H:%M:%S",
}
