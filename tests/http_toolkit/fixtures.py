import asyncio
from fastapi import FastAPI, HTTPException

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