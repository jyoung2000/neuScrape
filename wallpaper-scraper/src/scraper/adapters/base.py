"""Abstract base adapter for wallpaper scraping."""
from abc import ABC, abstractmethod
from typing import AsyncGenerator

from src.metadata.schemas import ScrapedImageInfo
from src.scraper.browser import BrowserManager


class BaseAdapter(ABC):
    """Base class for all scraping adapters."""

    def __init__(self, browser: BrowserManager):
        self.browser = browser

    @abstractmethod
    async def scrape(
        self, url: str, max_pages: int = 5
    ) -> AsyncGenerator[ScrapedImageInfo, None]:
        """Scrape wallpaper images from the given URL.

        Yields ScrapedImageInfo for each discovered wallpaper.
        """
        ...

    @abstractmethod
    async def can_handle(self, url: str) -> bool:
        """Check if this adapter can handle the given URL."""
        ...
