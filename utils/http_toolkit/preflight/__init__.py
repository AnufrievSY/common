import sys

from utils.http_toolkit.preflight.core.types import RedisConfig
from utils.http_toolkit.preflight import redis, doker
from utils.http_toolkit.preflight.core.utils import get_logger

log = get_logger()

def run() -> None:
    cfg = RedisConfig()
    try:
        doker.ensure()
        redis.ensure(cfg)
    except SystemExit:
        raise
    except Exception as e:
        log.error(e, exc_info=True)
        sys.exit(1)

if __name__ == '__main__':
    run()