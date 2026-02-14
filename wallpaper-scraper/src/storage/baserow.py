"""Baserow API client for uploading wallpapers and creating rows."""
import asyncio
from typing import Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.metadata.schemas import WallpaperRow
from src.utils.logging import get_logger

logger = get_logger("baserow")


class BaserowClient:
    """Client for Baserow table 810 — wallpaper database."""

    def __init__(
        self,
        api_url: str = "https://baserow.jymedia.cc",
        api_token: str = "",
        table_id: int = 810,
    ):
        self.api_url = api_url.rstrip("/")
        self.token = api_token
        self.table_id = table_id
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                headers={"Authorization": f"Token {self.token}"},
                timeout=httpx.Timeout(60.0),
                follow_redirects=True,
            )
        return self._client

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException)),
        reraise=True,
    )
    async def upload_file(self, jpeg_bytes: bytes, filename: str) -> dict:
        """Upload JPEG to Baserow file storage.

        Returns file object with 'name' key (Baserow internal filename).
        """
        client = await self._get_client()

        response = await client.post(
            f"{self.api_url}/api/user-files/upload-file/",
            files={"file": (filename, jpeg_bytes, "image/jpeg")},
        )
        response.raise_for_status()
        result = response.json()
        logger.info("Uploaded file: %s -> %s", filename, result.get("name"))
        return result

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException)),
        reraise=True,
    )
    async def create_row(self, row_data: dict) -> dict:
        """Create a row in the wallpaper table with user_field_names=true."""
        client = await self._get_client()

        response = await client.post(
            f"{self.api_url}/api/database/rows/table/{self.table_id}/",
            params={"user_field_names": "true"},
            json=row_data,
        )

        if response.status_code == 429:
            # Rate limited — wait and retry
            retry_after = int(response.headers.get("retry-after", "5"))
            logger.warning("Rate limited by Baserow, waiting %ds", retry_after)
            await asyncio.sleep(retry_after)
            raise httpx.TransportError("Rate limited")

        response.raise_for_status()
        result = response.json()
        logger.info("Created row: %s (id=%s)", row_data.get("wallpaperTitle", "?"), result.get("id"))
        return result

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException)),
        reraise=True,
    )
    async def check_hash_exists(self, img_hash: str) -> bool:
        """Check if a perceptual hash already exists in the table."""
        if not img_hash:
            return False

        client = await self._get_client()

        response = await client.get(
            f"{self.api_url}/api/database/rows/table/{self.table_id}/",
            params={
                "user_field_names": "true",
                "filter__imgHash__equal": img_hash,
            },
        )
        response.raise_for_status()
        data = response.json()
        exists = data.get("count", 0) > 0
        if exists:
            logger.debug("Hash %s already exists in Baserow", img_hash)
        return exists

    async def upload_wallpaper(
        self, jpeg_bytes: bytes, metadata: WallpaperRow
    ) -> dict:
        """Full upload: file upload + row creation.

        1. Upload JPEG to Baserow file storage
        2. Create row referencing the uploaded file with all metadata
        """
        # Step 1: Upload file
        filename = f"{metadata.imgHash}_{metadata.Width}x{metadata.Height}.jpg"
        file_obj = await self.upload_file(jpeg_bytes, filename)

        # Step 2: Create row with metadata
        row_data = metadata.to_baserow_dict()
        row_data["imageFile"] = [{"name": file_obj["name"]}]

        return await self.create_row(row_data)

    async def create_rows_batch(self, rows: list[dict]) -> list[dict]:
        """Create multiple rows in a single request (up to 200)."""
        if not rows:
            return []

        client = await self._get_client()
        results = []

        # Baserow batch endpoint supports up to 200 rows
        for i in range(0, len(rows), 200):
            batch = rows[i : i + 200]
            response = await client.post(
                f"{self.api_url}/api/database/rows/table/{self.table_id}/batch/",
                params={"user_field_names": "true"},
                json={"items": batch},
            )
            response.raise_for_status()
            data = response.json()
            results.extend(data.get("items", []))

        return results

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    @property
    def is_configured(self) -> bool:
        """Check if the client has a valid token."""
        return bool(self.token and self.token != "your_token_here")
