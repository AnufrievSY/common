import asyncio

import pytest

from api_toolkit.validator import IgnoreCondition, RetryCondition, TooMuchRetry, aio, sync


class Response:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        self.text = f"status={status_code}"


def test_sync_retry_then_success():
    retry = RetryCondition(status=[500], max_count=2, delay_sec=0)
    calls = {"count": 0}

    @sync(retry=retry)
    def fetch():
        calls["count"] += 1
        if calls["count"] < 3:
            return Response(500)
        return Response(200)

    result = fetch()
    assert result.status_code == 200
    assert calls["count"] == 3


def test_sync_retry_exhausted():
    retry = RetryCondition(status=[500], max_count=1, delay_sec=0)

    @sync(retry=retry)
    def fetch():
        return Response(500)

    with pytest.raises(TooMuchRetry):
        fetch()


def test_sync_ignore_exception():
    ignore = IgnoreCondition(exception=[ValueError], return_func=lambda _: "ignored")

    @sync(ignore=ignore)
    def fetch():
        raise ValueError("boom")

    assert fetch() == "ignored"


def test_async_ignore_status():
    ignore = IgnoreCondition(status=[404], return_func=lambda _: "ignored")

    @aio(ignore=ignore)
    async def fetch():
        class Resp:
            status = 404

        return Resp()

    assert asyncio.run(fetch()) == "ignored"
