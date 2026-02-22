import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


import pytest
import allure

from httpx import AsyncClient
from httpx._transports.asgi import ASGITransport
from fastapi.testclient import TestClient

from utils.http_toolkit import limiter
from utils.http_toolkit import validator
from utils.http_toolkit import cache

from fixtures import app, reset_state

@pytest.mark.http_toolkit
@pytest.mark.limiter
@pytest.mark.concurrency_limit
@pytest.mark.rate_limit
@pytest.mark.validator
@pytest.mark.cache
@allure.parent_suite("HTTP Toolkit")
@allure.epic("Все в одном")
@allure.title("sync run")
@allure.description(
    "Тест проверяет, корректность работы всех инструментов одновременно"
)
def test_all_in_one_sync():
    client = TestClient(app)
    reset_state()

    @limiter.concurrency_limit(limit=2)
    @limiter.rate_limit(limit=10, period=0)
    @validator.validate(retry=validator.RetryCondition(statuses=[429], delay_sec=10.0, max_count=1))
    @cache.cache(ttl=5)
    def fetch(method="GET", url="/sync_rate_test"):
        return client.request(method, url)

    actual = fetch()

    assert actual.status_code == 200


@pytest.mark.asyncio
@pytest.mark.http_toolkit
@pytest.mark.limiter
@pytest.mark.concurrency_limit
@pytest.mark.rate_limit
@pytest.mark.validator
@pytest.mark.cache
@allure.parent_suite("HTTP Toolkit")
@allure.epic("Все в одном")
@allure.title("async run")
@allure.description(
    "Тест проверяет, корректность работы всех инструментов одновременно"
)
def test_all_in_one_async():
    client = TestClient(app)
    reset_state()

    @limiter.concurrency_limit(limit=2)
    @limiter.rate_limit(limit=10, period=0)
    @validator.validate(retry=validator.RetryCondition(statuses=[429], delay_sec=10.0, max_count=1))
    @cache.cache(ttl=5)
    async def fetch(method="GET", url="/async_rate_test"):
        return client.request(method, url)

    actual = asyncio.run(fetch())

    assert actual.status_code == 200