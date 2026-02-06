import time
import asyncio
import threading
from fastapi import FastAPI, HTTPException

app = FastAPI()
async_semaphore = asyncio.Semaphore(1)
sync_semaphore = threading.Semaphore(1)


@app.get("/async_test")
async def async_test_endpoint():
    """
    Тестовый endpoint, который имитирует лимит параллельных запросов.
    Если semaphore уже заблокирован, возвращает 429.
    Иначе выполняет sleep(1) и возвращает 200.
    """
    if async_semaphore.locked():
        raise HTTPException(429, "Too Many Requests")
    await async_semaphore.acquire()
    try:
        await asyncio.sleep(1)
        return {"ok": True}
    finally:
        async_semaphore.release()

@app.get("/sync_test")
def synq_test_endpoint():
    """
    Тестовый endpoint, который имитирует лимит параллельных запросов.
    Если semaphore уже заблокирован, возвращает 429.
    Иначе выполняет sleep(1) и возвращает 200.
    """
    acquired = sync_semaphore.acquire(blocking=False)
    if not acquired:
        raise HTTPException(429, "Too Many Requests")

    try:
        time.sleep(1)
        return {"ok": True}
    finally:
        sync_semaphore.release()