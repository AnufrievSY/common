from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    import redis  # noqa: F401
except ModuleNotFoundError:
    class _RedisExceptions:
        ConnectionError = TimeoutError
        TimeoutError = TimeoutError

    class _RedisStub:
        exceptions = _RedisExceptions

        class Redis:
            def __init__(self, *args, **kwargs):
                pass

            def register_script(self, script: str):
                def runner(*, keys, args):
                    return 1

                return runner

    sys.modules["redis"] = _RedisStub()
