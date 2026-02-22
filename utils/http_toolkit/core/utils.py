import json, hashlib
from multidict import CIMultiDict, CIMultiDictProxy
from collections.abc import Mapping

async def to_hashkey(**kwargs) -> str:
    """Создает уникальный ключ на основании переданного запроса."""

    def _json_default(o):
        if isinstance(o, (CIMultiDict, CIMultiDictProxy)):
            return dict(o)
        if isinstance(o, Mapping):
            return dict(o)
        if isinstance(o, (bytes, bytearray)):
            return o.decode("utf-8", errors="replace")
        return repr(o)

    s = json.dumps(kwargs, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default = _json_default)
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