import json, hashlib

async def to_hashkey(**kwargs) -> str:
    """Создает уникальный ключ на основании переданного запроса."""
    s = json.dumps(kwargs, ensure_ascii=False,
                   sort_keys=True,  # гарантирует одинаковый порядок ключей
                   separators=(",", ":")  # убираем лишние пробелы чтобы строка всегда была одинаковой
                   )
    return hashlib.md5(s.encode("utf-8")).hexdigest()

async def extract_body(r, raise_exc = False):
    """Извлекает тело запроса или ответа"""
    if hasattr(r, "json"):
        return r.json()
    if hasattr(r, "body"):
        return r.body
    if hasattr(r, "text"):
        return r.text
    if raise_exc:
        raise ValueError("Тело не найдено или пустое")
    return None