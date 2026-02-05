import json, hashlib

def to_hashkey(**kwargs) -> str:
    """Создает уникальный ключ на основании переданного запроса."""
    # Превращаем dict в стабильную строку:
    # sort_keys=True — гарантирует одинаковый порядок ключей
    # separators — убираем лишние пробелы чтобы строка всегда была одинаковой
    s = json.dumps(kwargs, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.md5(s.encode("utf-8")).hexdigest()
