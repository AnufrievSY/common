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
from types import SimpleNamespace

import asyncio

from http_toolkit import validator
from tests.http_toolkit.fixtures import app, reset_state

@pytest.mark.http_toolkit
@pytest.mark.validator
@allure.parent_suite("HTTP Toolkit")
@allure.epic("Валидатор")
@allure.label("feature", "Запросы за единицу времени")
@allure.title("sync validate retry by status [200]")
@allure.description(
    "Тест проверяет, что при превышении лимита, "
    "срабатывает повторный запрос после паузы"
)
def test_sync_validate_retry_by_status_200():
    client = TestClient(app)
    reset_state()

    @validator.validate(retry=validator.RetryCondition(statuses=[429], delay_sec=10.0, max_count=1))
    def fetch():
        resp = client.get("/sync_rate_test")
        return resp

    with ThreadPoolExecutor(max_workers=10) as executor:
        tasks = {executor.submit(fetch) for _ in range(10)}
        results = {task.result().status_code for task in tasks}

        assert results == {200}

@pytest.mark.asyncio
@pytest.mark.http_toolkit
@pytest.mark.validator
@allure.parent_suite("HTTP Toolkit")
@allure.epic("Валидатор")
@allure.label("feature", "Запросы за единицу времени")
@allure.title("async validate retry by status [200]")
@allure.description(
    "Тест проверяет, что при превышении лимита, "
    "срабатывает повторный запрос после паузы"
)
async def test_async_validate_retry_by_status_200():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://async_rate_test") as client:
        reset_state()

        @validator.validate(retry=validator.RetryCondition(statuses=[429], delay_sec=10.0, max_count=1))
        async def fetch():
            resp = await client.get("/async_rate_test")
            return resp

        tasks = [asyncio.create_task(fetch()) for _ in range(10)]
        results = await asyncio.gather(*tasks)
        results = {resp.status_code for resp in results}
        assert set(results) == {200}

@pytest.mark.http_toolkit
@pytest.mark.validator
@allure.parent_suite("HTTP Toolkit")
@allure.epic("Валидатор")
@allure.label("feature", "Запросы за единицу времени")
@allure.title("sync validate retry by exception [200]")
@allure.description(
    "Тест проверяет, что при вызове ошибки, "
    "срабатывает повторный запрос после паузы"
)
def test_sync_validate_retry_by_exception_200():
    client = TestClient(app)
    reset_state()

    @validator.validate(retry=validator.RetryCondition(exceptions=[validator.TooMuchRetries], delay_sec=10.0, max_count=1))
    def fetch():
        resp = client.get("/sync_rate_test")
        if resp.status_code == 429:
            raise validator.TooMuchRetries('Too many retries')
        return resp

    with ThreadPoolExecutor(max_workers=10) as executor:
        tasks = {executor.submit(fetch) for _ in range(10)}
        results = {task.result().status_code for task in tasks}

        assert results == {200}

@pytest.mark.asyncio
@pytest.mark.http_toolkit
@pytest.mark.validator
@allure.parent_suite("HTTP Toolkit")
@allure.epic("Валидатор")
@allure.label("feature", "Запросы за единицу времени")
@allure.title("async validate retry by exception [200]")
@allure.description(
    "Тест проверяет, что при вызове ошибки, "
    "срабатывает повторный запрос после паузы"
)
async def test_async_validate_retry_by_exception_200():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://async_rate_test") as client:
        reset_state()

        @validator.validate(retry=validator.RetryCondition(exceptions=[validator.TooMuchRetries], delay_sec=10.0, max_count=1))
        async def fetch():
            resp = await client.get("/async_rate_test")
            if resp.status_code == 429:
                raise validator.TooMuchRetries('Too many retries')
            return resp

        tasks = [asyncio.create_task(fetch()) for _ in range(10)]
        results = await asyncio.gather(*tasks)
        results = {resp.status_code for resp in results}
        assert set(results) == {200}

@pytest.mark.http_toolkit
@pytest.mark.validator
@allure.parent_suite("HTTP Toolkit")
@allure.epic("Валидатор")
@allure.label("feature", "Запросы за единицу времени")
@allure.title("sync validate ignore by status [200, 429]")
@allure.description(
    "Тест проверяет, что при превышении лимита, "
    "срабатывает игнорирование его результатов и "
    "возврат ответа как есть"
)
def test_sync_validate_ignore_by_status_200_429():
    client = TestClient(app)
    reset_state()

    @validator.validate(ignore=validator.IgnoreCondition(statuses=[429]))
    def fetch():
        resp = client.get("/sync_rate_test")
        return resp

    with ThreadPoolExecutor(max_workers=10) as executor:
        tasks = {executor.submit(fetch) for _ in range(10)}
        results = {task.result().status_code for task in tasks}

        assert results == {200, 429}

@pytest.mark.asyncio
@pytest.mark.http_toolkit
@pytest.mark.validator
@allure.parent_suite("HTTP Toolkit")
@allure.epic("Валидатор")
@allure.label("feature", "Запросы за единицу времени")
@allure.title("async validate ignore by status [200, 429]")
@allure.description(
    "Тест проверяет, что при превышении лимита, "
    "срабатывает игнорирование его результатов и "
    "возврат ответа как есть"
)
async def test_async_validate_ignore_by_status_200_429():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://async_rate_test") as client:
        reset_state()

        @validator.validate(ignore=validator.IgnoreCondition(statuses=[429]))
        async def fetch():
            resp = await client.get("/async_rate_test")
            return resp

        tasks = [asyncio.create_task(fetch()) for _ in range(10)]
        results = await asyncio.gather(*tasks)
        results = {resp.status_code for resp in results}
        assert set(results) == {200, 429}

@pytest.mark.http_toolkit
@pytest.mark.validator
@allure.parent_suite("HTTP Toolkit")
@allure.epic("Валидатор")
@allure.label("feature", "Запросы за единицу времени")
@allure.title("sync validate ignore by exception [200, 429]")
@allure.description(
    "Тест проверяет, что при превышении лимита, "
    "срабатывает игнорирование его результатов и "
    "возврат ответа как есть"
)
def test_sync_validate_ignore_by_exception_200_429():
    client = TestClient(app)
    reset_state()

    @validator.validate(ignore=validator.IgnoreCondition(exceptions=[validator.TooMuchRetries],
                                                         return_func=lambda r: SimpleNamespace(status_code=429)))
    def fetch():
        resp = client.get("/sync_rate_test")
        if resp.status_code == 429:
            raise validator.TooMuchRetries('Too many retries')
        return resp

    with ThreadPoolExecutor(max_workers=10) as executor:
        tasks = {executor.submit(fetch) for _ in range(10)}
        results = {task.result().status_code for task in tasks}

        assert results == {200, 429}

@pytest.mark.asyncio
@pytest.mark.http_toolkit
@pytest.mark.validator
@allure.parent_suite("HTTP Toolkit")
@allure.epic("Валидатор")
@allure.label("feature", "Запросы за единицу времени")
@allure.title("async validate ignore by exception [200, 429]")
@allure.description(
    "Тест проверяет, что при превышении лимита, "
    "срабатывает игнорирование его результатов и "
    "возврат ответа как есть"
)
async def test_async_validate_ignore_by_exception_200_429():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://async_rate_test") as client:
        reset_state()

        @validator.validate(ignore=validator.IgnoreCondition(exceptions=[validator.TooMuchRetries],
                                                             return_func=lambda r: SimpleNamespace(status_code=429)))
        async def fetch():
            resp = await client.get("/async_rate_test")
            if resp.status_code == 429:
                raise validator.TooMuchRetries('Too many retries')
            return resp

        tasks = [asyncio.create_task(fetch()) for _ in range(10)]
        results = await asyncio.gather(*tasks)
        results = {resp.status_code for resp in results}
        assert set(results) == {200, 429}