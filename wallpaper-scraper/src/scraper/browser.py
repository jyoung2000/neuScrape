"""Headless Chromium browser manager via Playwright with stealth settings."""
import asyncio
import os
import random
from typing import Optional

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from src.utils.logging import get_logger

logger = get_logger("browser")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
]

# Cookie consent button selectors to auto-dismiss
COOKIE_CONSENT_SELECTORS = [
    "button[id*='accept']",
    "button[class*='accept']",
    "button[id*='consent']",
    "button[class*='consent']",
    "button[id*='agree']",
    "button[class*='agree']",
    "a[id*='accept']",
    "a[class*='accept']",
    "[class*='cookie'] button",
    "[id*='cookie'] button",
    "[class*='gdpr'] button",
    "[class*='consent-banner'] button",
    "#onetrust-accept-btn-handler",
    ".cc-accept",
    ".cc-dismiss",
]

# Resource types to block for speed
BLOCKED_RESOURCE_TYPES = {"font", "media"}


class BrowserManager:
    """Manages a headless Chromium browser for scraping."""

    def __init__(
        self,
        headless: bool = True,
        proxy: Optional[str] = None,
        block_resources: Optional[list[str]] = None,
        user_agent_rotation: bool = True,
    ):
        self.headless = headless
        self.proxy = proxy
        self.block_resources = set(block_resources or BLOCKED_RESOURCE_TYPES)
        self.user_agent_rotation = user_agent_rotation
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._started = False

    async def start(self) -> None:
        """Launch the browser."""
        if self._started:
            return
        self._playwright = await async_playwright().start()

        launch_args = {
            "headless": self.headless,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-gpu",
            ],
        }
        if self.proxy:
            launch_args["proxy"] = {"server": self.proxy}

        self._browser = await self._playwright.chromium.launch(**launch_args)
        self._started = True
        logger.info("Browser started (headless=%s)", self.headless)

    async def stop(self) -> None:
        """Close the browser and Playwright."""
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        self._started = False
        logger.info("Browser stopped")

    async def new_context(self) -> BrowserContext:
        """Create a new browser context with stealth settings."""
        if not self._started:
            await self.start()

        ua = random.choice(USER_AGENTS) if self.user_agent_rotation else USER_AGENTS[0]

        context = await self._browser.new_context(
            user_agent=ua,
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
            timezone_id="America/New_York",
            java_script_enabled=True,
            ignore_https_errors=True,
        )

        # Block unwanted resource types for speed
        if self.block_resources:
            await context.route(
                "**/*",
                lambda route: (
                    route.abort()
                    if route.request.resource_type in self.block_resources
                    else route.continue_()
                ),
            )

        return context

    async def new_page(self, context: Optional[BrowserContext] = None) -> Page:
        """Create a new page, optionally in an existing context."""
        if context is None:
            context = await self.new_context()

        page = await context.new_page()

        # Stealth: override navigator.webdriver
        await page.add_init_script(
            """
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            window.chrome = { runtime: {} };
            """
        )

        return page

    async def load_page(
        self,
        url: str,
        page: Optional[Page] = None,
        timeout: int = 30000,
        wait_for_idle: bool = True,
    ) -> Page:
        """Navigate to URL and wait for load. Returns the page."""
        if page is None:
            page = await self.new_page()

        try:
            await page.goto(url, timeout=timeout, wait_until="domcontentloaded")
            if wait_for_idle:
                try:
                    await page.wait_for_load_state("networkidle", timeout=15000)
                except Exception:
                    # networkidle can timeout on heavy pages — that's OK
                    pass
        except Exception as e:
            logger.warning("Failed to load %s: %s", url, e)
            raise

        # Auto-dismiss cookie consent
        await self._dismiss_cookies(page)

        return page

    async def scroll_page(
        self,
        page: Page,
        max_scrolls: int = 10,
        scroll_delay: float = 1.5,
    ) -> None:
        """Progressively scroll the page to trigger lazy-loaded content."""
        previous_height = await page.evaluate("document.body.scrollHeight")

        for i in range(max_scrolls):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(scroll_delay)

            new_height = await page.evaluate("document.body.scrollHeight")
            if new_height == previous_height:
                logger.debug("Scroll complete after %d scrolls (no new content)", i + 1)
                break
            previous_height = new_height

        # Scroll back to top
        await page.evaluate("window.scrollTo(0, 0)")

    async def _dismiss_cookies(self, page: Page) -> None:
        """Try to dismiss cookie consent popups."""
        for selector in COOKIE_CONSENT_SELECTORS:
            try:
                btn = page.locator(selector).first
                if await btn.is_visible(timeout=500):
                    await btn.click(timeout=1000)
                    logger.debug("Dismissed cookie popup with selector: %s", selector)
                    return
            except Exception:
                continue

    async def screenshot(self, page: Page, path: str) -> None:
        """Take a screenshot for debugging."""
        try:
            await page.screenshot(path=path, full_page=True)
            logger.debug("Screenshot saved to %s", path)
        except Exception as e:
            logger.warning("Screenshot failed: %s", e)

    @property
    def is_ready(self) -> bool:
        """Check if browser is running."""
        return self._started and self._browser is not None
