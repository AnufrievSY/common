# common

Набор утилит для API-клиентов: Redis-кеширование, глобальные лимитеры и валидатор ответов.

## Возможности

- Redis-кеширование для sync и async функций с TTL и ручной инвалидацией.
- Глобальные Redis-лимитеры: concurrency и rate (межпроцессные/межмашинные).
- Валидатор ответов для retry/ignore стратегий.

## Установка

### Через Git

```bash
pip install git+https://github.com/<org-or-user>/common.git
```

### Локально

```bash
git clone https://github.com/<org-or-user>/common.git
cd common
pip install -e .
```

## Быстрый старт

### Кеширование

```python
from api_toolkit import cache

@cache(ttl=60).sync
def get_orders(*, method, url, params=None, json=None, headers=None, cookies=None):
    ...

@cache(ttl=float("inf")).aio
async def get_orders_async(*, method, url, params=None, json=None, headers=None, cookies=None):
    ...
```

Инвалидация кеша:

```python
cfg = cache(ttl=60)
cfg.clear_prefix()  # удалить весь кеш по префиксу
cfg.invalidate(url="https://example.com/api", params={"q": "test"})
```

### Лимитеры

```python
from api_toolkit import concurrency_limit, rate_limit

limit_sync = concurrency_limit(limit=5, time_out=30)

@limit_sync.sync
def fetch(*, method, url, headers=None, cookies=None):
    ...

limit_async = rate_limit(limit=10, window=60)

@limit_async.aio
async def fetch_async(*, method, url, headers=None, cookies=None):
    ...
```

При необходимости можно передать готовый Redis клиент:

```python
import redis
from api_toolkit import rate_limit

client = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)
limiter = rate_limit(limit=10, window=60, redis_client=client)
```

### Валидатор ответов

```python
from api_toolkit import IgnoreCondition, RetryCondition, aio, sync

retry = RetryCondition(status=[500, 502], max_count=3, delay_sec=0.5)
ignore = IgnoreCondition(status=[404])

@sync(retry=retry, ignore=ignore)
def fetch(*, method, url):
    ...

@aio(retry=retry, ignore=ignore)
async def fetch_async(*, method, url):
    ...
```

## Интеграция в проекты

1. Установить пакет (Git или локально).
2. Импортировать нужные утилиты из `api_toolkit`.
3. Настроить Redis (host/port/db или общий клиент).

## Тесты

```bash
pytest
```
