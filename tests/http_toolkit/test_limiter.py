import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))  # Поднимаем корень проекта

import pytest
import asyncio
from fastapi import FastAPI, HTTPException
from httpx import AsyncClient
from http_toolkit import limiter
import allure
from httpx._transports.asgi import ASGITransport

# -----------------------
# FastAPI приложение
# -----------------------
app = FastAPI()
semaphore = asyncio.Semaphore(1)


@app.get("/test")
async def _test_endpoint():
    """
    Тестовый endpoint, который имитирует лимит параллельных запросов.
    Если semaphore уже заблокирован, возвращает 429.
    Иначе выполняет sleep(1) и возвращает 200.
    """
    if semaphore.locked():
        raise HTTPException(429, "Too Many Requests")
    await semaphore.acquire()
    try:
        await asyncio.sleep(1)
        return {"ok": True}
    finally:
        semaphore.release()


# =======================
# Тесты
# =======================

@pytest.mark.asyncio
@pytest.mark.http_toolkit
@pytest.mark.limiter
@pytest.mark.concurrency_limit
@allure.parent_suite("HTTP Toolkit")
@allure.epic("Лимитер")
@allure.label("feature", "Параллельные запросы")
@allure.title("Лимит параллельных запросов [200, 429]")
@allure.description(
    "Тест проверяет, что при превышении установленных "
    "лимитов параллельных запросов возвращается код 429."
)
async def test_limit_200_429():
    """
    Тест проверяет работу limiter.concurrency_limit с лимитом 10,
    ожидается, что один из параллельных запросов вернет 429.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:

        @limiter.concurrency_limit(limit=10)
        async def fetch():
            resp = await client.get("/test")
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
@allure.title("Лимит параллельных запросов [200, 200]")
@allure.description(
    "Тест проверяет, что даже при ограничении 1 параллельный запрос "
    "- лимитер корректно пропускает оба запроса (оба вернут 200)."
)
async def test_limit_200_200():
    """
    Тест проверяет работу limiter.concurrency_limit с лимитом 1,
    оба параллельных запроса должны вернуться 200.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:

        @limiter.concurrency_limit(limit=1)
        async def fetch():
            resp = await client.get("/test")
            return resp.status_code

        t1 = asyncio.create_task(fetch())
        t2 = asyncio.create_task(fetch())

        r1 = await t1
        r2 = await t2

        assert {r1, r2} == {200, 200}
