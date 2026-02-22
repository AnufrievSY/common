from functools import wraps
from pathlib import Path
from typing import Callable, Any


def has_extension(ext: str, raise_not_found: bool = False):
    """Проверяет, относится ли файл к указанному расширению."""
    def decorator(func: Callable[..., Any]):
        @wraps(func)
        def wrapper(**kwargs):
            file_path = kwargs.get('file_path')
            if not file_path:
                raise ValueError("Аргумент 'file_path' не найден.")
            if Path(file_path).suffix[1:] != ext:
                raise ValueError(f"Файл {file_path} имеет неверное расширение. Ожидалось {ext}")
            if not Path(file_path).exists() and raise_not_found:
                raise FileNotFoundError(f"Файл {file_path} не найден.")
            return func(**kwargs)
        return wrapper
    return decorator
