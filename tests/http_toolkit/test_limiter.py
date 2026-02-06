import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))  # Поднимаем корень проекта

import pytest
import allure

from httpx import AsyncClient
from httpx._transports.asgi import ASGITransport
from fastapi.testclient import TestClient
from concurrent.futures import ThreadPoolExecutor

import asyncio

from http_toolkit import limiter
from tests.http_toolkit.fixtures import app

@pytest.mark.http_toolkit
@pytest.mark.limiter
@pytest.mark.concurrency_limit
@allure.parent_suite("HTTP Toolkit")
@allure.epic("Лимитер")
@allure.label("feature", "Параллельные запросы")
@allure.title("Лимит синхронных параллельных запросов [200, 429]")
@allure.description(
    "Тест проверяет, что при превышении установленных "
    "лимитов параллельных запросов совершенных синхронной функции "
    "возвращается код 429"
)
def test_sync_limit_200_429():
    client = TestClient(app)

    @limiter.concurrency_limit(limit=10)
    def fetch():
        resp = client.get("/sync_test")
        return resp.status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        tasks = {executor.submit(fetch) for _ in range(2)}
        results = {task.result() for task in tasks}

        assert results == {200, 429}


@pytest.mark.http_toolkit
@pytest.mark.limiter
@pytest.mark.concurrency_limit
@allure.parent_suite("HTTP Toolkit")
@allure.epic("Лимитер")
@allure.label("feature", "Параллельные запросы")
@allure.title("Лимит синхронных параллельных запросов [200, 200]")
@allure.description(
    "Тест проверяет, что даже при ограничении 1 параллельный запрос "
    "совершенных синхронной функцией лимитер корректно отрабатывает "
    "возвращая 200 статус"
)
def test_sync_limit_200_200():
    client = TestClient(app)

    @limiter.concurrency_limit(limit=1)
    def fetch():
        resp = client.get("/sync_test")
        return resp.status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        tasks = {executor.submit(fetch) for _ in range(2)}
        results = {task.result() for task in tasks}

        assert results == {200, 429}

@pytest.mark.asyncio
@pytest.mark.http_toolkit
@pytest.mark.limiter
@pytest.mark.concurrency_limit
@allure.parent_suite("HTTP Toolkit")
@allure.epic("Лимитер")
@allure.label("feature", "Параллельные запросы")
@allure.title("Лимит асинхронных параллельных запросов [200, 429]")
@allure.description(
    "Тест проверяет, что при превышении установленных "
    "лимитов параллельных запросов совершенных асинхронной функцией "
    "возвращается код 429"
)
async def test_async_limit_200_429():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://async_test") as client:

        @limiter.concurrency_limit(limit=10)
        async def fetch():
            resp = await client.get("/async_test")
            return resp.status_code

        t1 = asyncio.create_task(fetch())
        t2 = asyncio.create_task(fetch())

        r1 = await t1
        r2 = await t2

        assert {r1, r2} == {200, 429}


@pytest.mark.asyncio
@pytest.mark.http_toolkit
@pytest.mark.limiter
@pytest.mark.concurrency_limit
@allure.parent_suite("HTTP Toolkit")
@allure.epic("Лимитер")
@allure.label("feature", "Параллельные запросы")
@allure.title("Лимит асинхронных параллельных запросов [200, 200]")
@allure.description(
    "Тест проверяет, что даже при ограничении 1 параллельный запрос "
    "совершенных асинхронной функцией лимитер корректно отрабатывает "
    "возвращая 200 статус"
)
async def test_limit_200_200():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://async_test") as client:

        @limiter.concurrency_limit(limit=1)
        async def fetch():
            resp = await client.get("/async_test")
            return resp.status_code

        t1 = asyncio.create_task(fetch())
        t2 = asyncio.create_task(fetch())

        r1 = await t1
        r2 = await t2

        assert {r1, r2} == {200, 200}
