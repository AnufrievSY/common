import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


import pytest
import allure

from httpx import AsyncClient
from httpx._transports.asgi import ASGITransport
from fastapi.testclient import TestClient

from utils.http_toolkit import Cache
from fixtures import app, reset_state

@pytest.mark.http_toolkit
@pytest.mark.cache
@allure.parent_suite("HTTP Toolkit")
@allure.epic("Кэширование")
@allure.title("sync cache")
@allure.description(
    "Тест проверяет, что при синхронном вызове, данные кэшируются"
)
def test_sync_cache():
    client = TestClient(app)
    reset_state()

    with Cache(ttl=5) as cache:
        r1 = cache.wrap(client.request, "get", "/sync_rate_test")
        r2 = cache.wrap(client.request, "get", "/sync_rate_test")

    try:
        r2.request
    except RuntimeError as exc:
        assert str(exc) == 'The request instance has not been set on this response.'

    assert r1.status_code == 200
    assert r2.status_code == 200

    assert r1.json() == r2.json()


@pytest.mark.asyncio
@pytest.mark.http_toolkit
@pytest.mark.cache
@allure.parent_suite("HTTP Toolkit")
@allure.epic("Кэширование")
@allure.title("sync cache")
@allure.description(
    "Тест проверяет, что при асинхронном вызове, данные кэшируются"
)
async def test_async_cache():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://async_rate_test") as client:
        reset_state()

        with Cache(ttl=5) as cache:
            r1 = await cache.wrap(client.request, "get", "/async_rate_test")
            r2 = await cache.wrap(client.request, "get", "/async_rate_test")

        try:
            r2.request
        except RuntimeError as exc:
            assert str(exc) == 'The request instance has not been set on this response.'

        assert r1.status_code == 200
        assert r2.status_code == 200

        assert r1.json() == r2.json()

