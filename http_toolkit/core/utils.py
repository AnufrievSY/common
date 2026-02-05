import json, hashlib

async def to_hashkey(**kwargs) -> str:
    """Создает уникальный ключ на основании переданного запроса."""
    s = json.dumps(kwargs, ensure_ascii=False,
                   sort_keys=True,  # гарантирует одинаковый порядок ключей
                   separators=(",", ":")  # убираем лишние пробелы чтобы строка всегда была одинаковой
                   )
    return hashlib.md5(s.encode("utf-8")).hexdigest()

async def extract_body(**kwargs):
    """Извлекает тело запроса"""
    for key in ["json", "data", "body"]:
        if key in kwargs and kwargs.get(key) is not None:
            return kwargs[key]
    raise ValueError("Тело запроса не найдено или пустое")