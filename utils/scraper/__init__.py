from pathlib import Path
from typing import Optional
from playwright.async_api import async_playwright, BrowserContext


class BaseScraper:
    """Базовый асинхронный скрапер на Chromium"""
    def __init__(self, headless: bool = False, profile_path: str | Path = None):
        """
            Инициализация скрапера
            Args:
                headless: Запуск браузера в режиме headless
                profile_path: Путь к профилю браузера
        """

        self.context = {}
        self.playwright = None
        self.browser: Optional[BrowserContext] = None

        self._context_setup(headless, profile_path)

    def _context_setup(self, headless: bool = False, profile_path: str | Path = None):
        """Формирует конфигурацию запуска браузера"""
        self.context = {
            "user_data_dir": profile_path,
            "headless": headless,
            "viewport": {"width": 1280, "height": 900},
            "record_har_path": None,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--no-default-browser-check",
            ],
        }

    async def open(self):
        """Запускает Playwright и открывает persistent-контекст Chromium"""
        self.playwright = await async_playwright().start()
        browser_type = self.playwright.chromium
        self.browser = await browser_type.launch_persistent_context(**self.context)

    async def close(self):
        """Корректно закрывает контекст и останавливает Playwright"""
        await self.browser.close()
        await self.playwright.stop()
