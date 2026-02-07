import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import preflight
preflight.run()

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
@allure.title("sync concurrency_limit [200, 429]")
@allure.description(
    "Тест проверяет, что при превышении установленных "
    "лимитов параллельных запросов совершенных синхронной "
    "функции возвращается код 429"
)
def test_sync_concurrency_limit_200_429():
    client = TestClient(app)

    @limiter.concurrency_limit(limit=10)
    def fetch():
        resp = client.get("/sync_test")
        return resp.status_code

    with ThreadPoolExecutor(max_workers=10) as executor:
        tasks = {executor.submit(fetch) for _ in range(10)}
        results = {task.result() for task in tasks}

        assert results == {200, 429}


@pytest.mark.http_toolkit
@pytest.mark.limiter
@pytest.mark.concurrency_limit
@allure.parent_suite("HTTP Toolkit")
@allure.epic("Лимитер")
@allure.label("feature", "Параллельные запросы")
@allure.title("sync concurrency_limit [200, 200]")
@allure.description(
    "Тест проверяет, корректное срабатывание лимитера при установленных "
    "ограничениях на количество параллельных запросов синхронной функцией"
)
def test_sync_concurrency_limit_200_200():
    client = TestClient(app)

    @limiter.concurrency_limit(limit=2)
    def fetch():
        resp = client.get("/sync_test")
        return resp.status_code

    with ThreadPoolExecutor(max_workers=10) as executor:
        tasks = {executor.submit(fetch) for _ in range(10)}
        results = {task.result() for task in tasks}

        assert results == {200}

@pytest.mark.asyncio
@pytest.mark.http_toolkit
@pytest.mark.limiter
@pytest.mark.concurrency_limit
@allure.parent_suite("HTTP Toolkit")
@allure.epic("Лимитер")
@allure.label("feature", "Параллельные запросы")
@allure.title("async concurrency_limit  [200, 429]")
@allure.description(
    "Тест проверяет, что при превышении установленных "
    "лимитов параллельных запросов совершенных асинхронной "
    "функцией возвращается код 429"
)
async def test_async_concurrency_limit_200_429():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://async_test") as client:

        @limiter.concurrency_limit(limit=10)
        async def fetch():
            resp = await client.get("/async_test")
            return resp.status_code

        tasks = [asyncio.create_task(fetch()) for _ in range(10)]
        results = await asyncio.gather(*tasks)

        assert set(results) == {200, 429}


@pytest.mark.asyncio
@pytest.mark.http_toolkit
@pytest.mark.limiter
@pytest.mark.concurrency_limit
@allure.parent_suite("HTTP Toolkit")
@allure.epic("Лимитер")
@allure.label("feature", "Параллельные запросы")
@allure.title("async concurrency_limit  [200, 200]")
@allure.description(
    "Тест проверяет, корректное срабатывание лимитера при установленных "
    "ограничениях на количество параллельных запросов асинхронной функцией"
)
async def test_async_concurrency_limit_200_200():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://async_test") as client:

        @limiter.concurrency_limit(limit=2)
        async def fetch():
            resp = await client.get("/async_test")
            return resp.status_code

        tasks = [asyncio.create_task(fetch()) for _ in range(10)]
        results = await asyncio.gather(*tasks)

        assert set(results) == {200}

@pytest.mark.http_toolkit
@pytest.mark.limiter
@pytest.mark.rate_limit
@allure.parent_suite("HTTP Toolkit")
@allure.epic("Лимитер")
@allure.label("feature", "Запросы за единицу времени")
@allure.title("sync rate_limit [200, 429]")
@allure.description(
    "Тест проверяет, что при превышении установленных "
    "лимитов последовательных запросов за единицу времени "
    "совершенных синхронной функции возвращается код 429"
)
def test_sync_rate_limit_200_429():
    client = TestClient(app)

    @limiter.rate_limit(limit=10, period=0)
    def fetch():
        resp = client.get("/sync_test")
        return resp.status_code

    with ThreadPoolExecutor(max_workers=10) as executor:
        tasks = {executor.submit(fetch) for _ in range(10)}
        results = {task.result() for task in tasks}

        assert results == {200, 429}


@pytest.mark.http_toolkit
@pytest.mark.rate_limit
@pytest.mark.concurrency_limit
@allure.parent_suite("HTTP Toolkit")
@allure.epic("Лимитер")
@allure.label("feature", "Запросы за единицу времени")
@allure.title("sync rate_limit [200, 200]")
@allure.description(
    "Тест проверяет, корректное срабатывание лимитера при установленных "
    "ограничениях на количество параллельных запросов синхронной функцией"
)
def test_sync_rate_limit_200_200():
    client = TestClient(app)

    @limiter.rate_limit(limit=5, period=10)
    def fetch():
        resp = client.get("/sync_test")
        return resp.status_code

    with ThreadPoolExecutor(max_workers=10) as executor:
        tasks = {executor.submit(fetch) for _ in range(10)}
        results = {task.result() for task in tasks}

        assert results == {200}

@pytest.mark.asyncio
@pytest.mark.http_toolkit
@pytest.mark.limiter
@pytest.mark.rate_limit
@allure.parent_suite("HTTP Toolkit")
@allure.epic("Лимитер")
@allure.label("feature", "Запросы за единицу времени")
@allure.title("sync rate_limit [200, 429]")
@allure.description(
    "Тест проверяет, что при превышении установленных "
    "лимитов последовательных запросов за единицу времени "
    "совершенных aсинхронной функции возвращается код 429"
)
async def test_async_rate_limit_200_429():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://async_test") as client:

        @limiter.rate_limit(limit=100, period=0)
        async def fetch():
            resp = await client.get("/async_test")
            return resp.status_code

        tasks = [asyncio.create_task(fetch()) for _ in range(10)]
        results = await asyncio.gather(*tasks)

        assert set(results) == {200, 429}


@pytest.mark.asyncio
@pytest.mark.http_toolkit
@pytest.mark.limiter
@pytest.mark.rate_limit
@allure.parent_suite("HTTP Toolkit")
@allure.epic("Лимитер")
@allure.label("feature", "Запросы за единицу времени")
@allure.title("sync rate_limit [200, 200]")
@allure.description(
    "Тест проверяет, корректное срабатывание лимитера при установленных "
    "ограничениях на количество параллельных запросов aсинхронной функцией"
)
async def test_async_rate_limit_200_200():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://async_test") as client:

        @limiter.rate_limit(limit=5, period=10)
        async def fetch():
            resp = await client.get("/async_test")
            return resp.status_code

        tasks = [asyncio.create_task(fetch()) for _ in range(10)]
        results = await asyncio.gather(*tasks)

        assert set(results) == {200}
