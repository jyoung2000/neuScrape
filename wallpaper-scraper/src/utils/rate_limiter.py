"""Simple async rate limiter for polite scraping."""
import asyncio
import random
import time


class RateLimiter:
    """Token bucket rate limiter with jitter."""

    def __init__(self, delay_seconds: float = 2.0, jitter: float = 1.0):
        self.delay = delay_seconds
        self.jitter = jitter
        self._last_request = 0.0
        self._lock = asyncio.Lock()

    async def wait(self) -> None:
        """Wait until it's safe to make the next request."""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request
            wait_time = self.delay + random.uniform(0, self.jitter)

            if elapsed < wait_time:
                await asyncio.sleep(wait_time - elapsed)

            self._last_request = time.monotonic()

    def set_delay(self, delay_seconds: float) -> None:
        """Update the delay between requests."""
        self.delay = delay_seconds
