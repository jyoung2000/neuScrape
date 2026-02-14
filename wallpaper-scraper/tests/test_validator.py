"""Tests for image validation."""
import io

import pytest
from PIL import Image

from src.downloader.validator import validate_image


def _make_image(width, height, fmt="JPEG"):
    """Create test image bytes."""
    img = Image.new("RGB", (width, height), (100, 150, 200))
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


class TestValidateImage:
    def test_valid_1920x1080(self):
        data = _make_image(1920, 1080)
        result = validate_image(data)
        assert result.valid is True
        assert result.width == 1920
        assert result.height == 1080
        assert result.aspect_ratio == "16:9"
        assert result.is_mobile is False
        assert result.phash != ""

    def test_valid_4k(self):
        data = _make_image(3840, 2160)
        result = validate_image(data)
        assert result.valid is True
        assert result.width == 3840
        assert result.height == 2160

    def test_valid_portrait(self):
        data = _make_image(1080, 1920)
        result = validate_image(data)
        assert result.valid is True
        assert result.is_mobile is True

    def test_too_small(self):
        data = _make_image(400, 300)
        result = validate_image(data)
        assert result.valid is False
        assert "small" in result.error.lower()

    def test_below_minimum(self):
        data = _make_image(1280, 720)
        result = validate_image(data)
        assert result.valid is False

    def test_invalid_data(self):
        result = validate_image(b"not an image")
        assert result.valid is False
        assert result.error is not None

    def test_phash_generated(self):
        data = _make_image(1920, 1080)
        result = validate_image(data)
        assert result.valid is True
        assert len(result.phash) > 0

    def test_file_too_large(self):
        # Create a very small image but set max_file_size_mb=0
        data = _make_image(1920, 1080)
        result = validate_image(data, max_file_size_mb=0)
        assert result.valid is False
        assert "large" in result.error.lower()
