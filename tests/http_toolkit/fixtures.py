import time
import asyncio
import threading
from collections import deque
from fastapi import FastAPI, HTTPException

WINDOW_SECONDS = 10
MAX_REQUESTS_PER_WINDOW = 5
MAX_CONCURRENT_REQUESTS = 2

app = FastAPI()

async_semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
async_rate_lock = asyncio.Lock()
async_request_times = deque()

sync_semaphore = threading.Semaphore(MAX_CONCURRENT_REQUESTS)
sync_rate_lock = threading.Lock()
sync_request_times = deque()


def _purge_old_requests(request_times: deque, now: float) -> None:
    cutoff = now - WINDOW_SECONDS
    while request_times and request_times[0] <= cutoff:
        request_times.popleft()


async def _async_rate_limited() -> bool:
    now = time.monotonic()
    async with async_rate_lock:
        _purge_old_requests(async_request_times, now)
        if len(async_request_times) >= MAX_REQUESTS_PER_WINDOW:
            return True
        async_request_times.append(now)
        return False


def _sync_rate_limited() -> bool:
    now = time.monotonic()
    with sync_rate_lock:
        _purge_old_requests(sync_request_times, now)
        if len(sync_request_times) >= MAX_REQUESTS_PER_WINDOW:
            return True
        sync_request_times.append(now)
        return False


@app.get("/async_test")
async def async_test_endpoint():
    """Тестовый endpoint, который имитирует лимит параллельных запросов
    и лимит запросов за минуту.
    """
    try:
        await asyncio.wait_for(async_semaphore.acquire(), timeout=0)
    except asyncio.TimeoutError:
        raise HTTPException(429, "Too Many Requests")
    await async_semaphore.acquire()

    try:
        if await _async_rate_limited():
            raise HTTPException(429, "Too Many Requests")
        await asyncio.sleep(1)
        return {"ok": True}
    finally:
        async_semaphore.release()

@app.get("/sync_test")
def synq_test_endpoint():
    """
    Тестовый endpoint, который имитирует лимит параллельных запросов
    и лимит запросов за минуту.
    """
    acquired = sync_semaphore.acquire(blocking=False)
    if not acquired:
        raise HTTPException(429, "Too Many Requests")

    try:
        if _sync_rate_limited():
            raise HTTPException(429, "Too Many Requests")
        time.sleep(1)
        return {"ok": True}
    finally:
        sync_semaphore.release()