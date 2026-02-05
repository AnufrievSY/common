import fnmatch

from api_toolkit.cache import cache


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, bytes] = {}

    def get(self, key: str):
        return self.store.get(key)

    def set(self, key: str, value: bytes):
        self.store[key] = value
        return True

    def setex(self, key: str, ttl: int, value: bytes):
        self.store[key] = value
        return True

    def delete(self, *keys: str):
        removed = 0
        for key in keys:
            if key in self.store:
                removed += 1
                del self.store[key]
        return removed

    def scan(self, *, cursor: int = 0, match: str, count: int = 1000):
        keys = [k for k in self.store.keys() if fnmatch.fnmatch(k, match)]
        return 0, keys

    def flushdb(self):
        self.store.clear()
        return True


def test_cache_sync_hit():
    cfg = cache(ttl=60)
    fake = FakeRedis()
    object.__setattr__(cfg, "_client", fake)

    calls = {"count": 0}

    @cfg.sync
    def fetch(value: int):
        calls["count"] += 1
        return {"value": value}

    assert fetch(10) == {"value": 10}
    assert fetch(10) == {"value": 10}
    assert calls["count"] == 1


def test_cache_disabled_ttl_none():
    cfg = cache(ttl=None)
    calls = {"count": 0}

    @cfg.sync
    def fetch(value: int):
        calls["count"] += 1
        return {"value": value}

    assert fetch(1) == {"value": 1}
    assert fetch(1) == {"value": 1}
    assert calls["count"] == 2


def test_cache_invalidate_http_style():
    cfg = cache(ttl=60)
    fake = FakeRedis()
    object.__setattr__(cfg, "_client", fake)

    @cfg.sync
    def fetch(*, method: str, url: str, params=None):
        return {"ok": True}

    fetch(method="GET", url="https://example.com", params={"q": "a"})
    fetch(method="GET", url="https://example.com", params={"q": "b"})

    deleted = cfg.invalidate(url="https://example.com")
    assert deleted == 2
