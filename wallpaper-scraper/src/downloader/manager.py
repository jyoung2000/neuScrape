"""Async download manager with connection pooling and retry."""
import asyncio
from typing import Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from src.utils.logging import get_logger

logger = get_logger("downloader")

# Content types that indicate an image
IMAGE_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/bmp",
    "image/tiff",
    "image/gif",
}


class DownloadManager:
    """Async image download manager with concurrency control."""

    def __init__(
        self,
        max_concurrent: int = 5,
        max_file_size_mb: int = 50,
        timeout: float = 60.0,
    ):
        self.max_concurrent = max_concurrent
        self.max_file_size_bytes = max_file_size_mb * 1024 * 1024
        self.timeout = timeout
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                follow_redirects=True,
                http2=True,
                limits=httpx.Limits(
                    max_connections=self.max_concurrent * 2,
                    max_keepalive_connections=self.max_concurrent,
                ),
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                    "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
                },
            )
        return self._client

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def download(self, url: str) -> Optional[bytes]:
        """Download an image from URL with retry.

        Returns image bytes or None if download fails validation.
        """
        async with self._semaphore:
            client = await self._get_client()

            try:
                # HEAD request first to check content type and size
                head_resp = await client.head(url)
                content_type = head_resp.headers.get("content-type", "").split(";")[0].strip()
                content_length = head_resp.headers.get("content-length")

                if content_type and content_type not in IMAGE_CONTENT_TYPES:
                    # Some servers don't return correct content-type for HEAD
                    # Only skip if it's clearly not an image (e.g., text/html)
                    if content_type.startswith("text/"):
                        logger.debug("Skipping non-image URL (%s): %s", content_type, url)
                        return None

                if content_length:
                    size = int(content_length)
                    if size > self.max_file_size_bytes:
                        logger.debug(
                            "Skipping oversized image (%d MB): %s",
                            size // (1024 * 1024),
                            url,
                        )
                        return None

                # Stream download
                data = bytearray()
                async with client.stream("GET", url) as response:
                    response.raise_for_status()

                    async for chunk in response.aiter_bytes(chunk_size=65536):
                        data.extend(chunk)
                        if len(data) > self.max_file_size_bytes:
                            logger.debug("Download exceeded max size, aborting: %s", url)
                            return None

                if len(data) < 1024:
                    logger.debug("Downloaded file too small (%d bytes): %s", len(data), url)
                    return None

                logger.info("Downloaded %d KB from %s", len(data) // 1024, url)
                return bytes(data)

            except httpx.HTTPStatusError as e:
                logger.warning("HTTP %d downloading %s", e.response.status_code, url)
                raise
            except Exception as e:
                logger.warning("Download failed for %s: %s", url, e)
                raise

    async def download_batch(
        self, urls: list[str]
    ) -> dict[str, Optional[bytes]]:
        """Download multiple images concurrently.

        Returns dict mapping URL -> bytes (or None for failures).
        """
        tasks = {url: asyncio.create_task(self._safe_download(url)) for url in urls}
        results = {}
        for url, task in tasks.items():
            results[url] = await task
        return results

    async def _safe_download(self, url: str) -> Optional[bytes]:
        """Download with error catching (no re-raise)."""
        try:
            return await self.download(url)
        except Exception as e:
            logger.error("Failed to download %s after retries: %s", url, e)
            return None

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
