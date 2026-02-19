import pytest
import allure

import logging
from utils.logger import get_logger

@pytest.mark.logger
@allure.parent_suite("Logger")
@allure.epic("Логировщик")
@allure.title("Логирование")
@allure.description("Тест проверяет, корректность работы логгера")
def test_logger(caplog):
    log = get_logger(name="test_logger", lvl="DEBUG").logger

    log.addHandler(caplog.handler)

    try:
        with caplog.at_level(logging.INFO):
            log.info("info")
    finally:
        log.removeHandler(caplog.handler)

    assert len(caplog.records) == 1
    r = caplog.records[0]
    assert r.levelno == logging.INFO
    assert r.getMessage() == "info"
