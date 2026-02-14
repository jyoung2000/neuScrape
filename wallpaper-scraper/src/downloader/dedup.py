"""Perceptual hash deduplication for wallpaper images."""
from typing import Optional

import imagehash

from src.utils.logging import get_logger

logger = get_logger("dedup")


class DeduplicationChecker:
    """Check for duplicate wallpapers using perceptual hashing."""

    def __init__(self, hamming_threshold: int = 8):
        self.hamming_threshold = hamming_threshold
        self._session_hashes: dict[str, str] = {}  # hash_str -> image_url

    def is_duplicate_in_session(self, phash_str: str) -> Optional[str]:
        """Check if hash matches any in the current session.

        Returns the URL of the duplicate if found, None otherwise.
        """
        if not phash_str:
            return None

        try:
            new_hash = imagehash.hex_to_hash(phash_str)
        except Exception:
            return None

        for existing_hash_str, url in self._session_hashes.items():
            try:
                existing_hash = imagehash.hex_to_hash(existing_hash_str)
                distance = new_hash - existing_hash
                if distance <= self.hamming_threshold:
                    logger.debug(
                        "Duplicate found (distance=%d): %s matches %s",
                        distance,
                        phash_str,
                        existing_hash_str,
                    )
                    return url
            except Exception:
                continue

        return None

    def add_hash(self, phash_str: str, image_url: str) -> None:
        """Register a hash in the session."""
        if phash_str:
            self._session_hashes[phash_str] = image_url

    def clear(self) -> None:
        """Clear session hashes."""
        self._session_hashes.clear()

    @property
    def count(self) -> int:
        """Number of hashes in session."""
        return len(self._session_hashes)
