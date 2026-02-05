import json, hashlib

def to_hashkey(**kwargs) -> str:
    """Создает уникальный ключ на основании переданного запроса."""
    s = json.dumps(kwargs, ensure_ascii=False,
                   sort_keys=True,  # гарантирует одинаковый порядок ключей
                   separators=(",", ":")  # убираем лишние пробелы чтобы строка всегда была одинаковой
                   )
    return hashlib.md5(s.encode("utf-8")).hexdigest()
