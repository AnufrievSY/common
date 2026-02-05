from api_toolkit._common import to_hashkey
from api_toolkit.limiter import concurrency_limit, rate_limit


class FakeRedis:
    def __init__(self) -> None:
        self.zrem_calls: list[tuple[str, str]] = []

    def register_script(self, script: str):
        def runner(*, keys, args):
            return 1

        return runner

    def zrem(self, key: str, token: str):
        self.zrem_calls.append((key, token))
        return 1


def test_concurrency_limit_releases_slot():
    fake = FakeRedis()
    limiter = concurrency_limit(limit=1, time_out=5, redis_client=fake)

    @limiter.sync
    def fetch(*, method: str, url: str):
        return "ok"

    assert fetch(method="GET", url="https://example.com") == "ok"
    assert len(fake.zrem_calls) == 1


def test_rate_limit_key_builder():
    fake = FakeRedis()
    limiter = rate_limit(limit=3, window=10, redis_client=fake)

    key = limiter._key(method="GET", url="https://example.com", headers={"h": "1"}, cookies=None)
    expected = to_hashkey(method="GET", url="https://example.com", headers={"h": "1"}, cookies=None)
    assert key == f"rate_limit:{expected}"
