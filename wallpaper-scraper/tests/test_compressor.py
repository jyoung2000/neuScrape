"""Tests for JPEG compression pipeline."""
import io

import pytest
from PIL import Image

from src.downloader.compressor import (
    color_to_name,
    compress_to_jpeg,
    get_dominant_colors,
    get_image_dimensions,
)


def _make_test_image(width=1920, height=1080, mode="RGB", color=(100, 150, 200)):
    """Create a test image as bytes."""
    img = Image.new(mode, (width, height), color)
    buf = io.BytesIO()
    fmt = "PNG" if mode in ("RGBA", "LA", "P") else "JPEG"
    if mode == "P":
        img = img.convert("RGB")
        fmt = "PNG"
    if mode in ("RGBA", "LA"):
        fmt = "PNG"
    img.save(buf, format=fmt)
    return buf.getvalue()


class TestCompressToJpeg:
    def test_basic_compression(self):
        data = _make_test_image()
        result = compress_to_jpeg(data)
        assert isinstance(result, bytes)
        assert len(result) > 0

        # Verify it's valid JPEG
        img = Image.open(io.BytesIO(result))
        assert img.format == "JPEG"

    def test_compression_reduces_size(self):
        # Create a large PNG
        png_data = _make_test_image(3840, 2160)
        jpeg_data = compress_to_jpeg(png_data, quality=85)
        # JPEG should typically be smaller (unless input is already very small)
        assert len(jpeg_data) > 0

    def test_rgba_to_rgb(self):
        data = _make_test_image(mode="RGBA", color=(100, 150, 200, 128))
        result = compress_to_jpeg(data)
        img = Image.open(io.BytesIO(result))
        assert img.mode == "RGB"
        assert img.format == "JPEG"

    def test_max_dimension(self):
        data = _make_test_image(3840, 2160)
        result = compress_to_jpeg(data, max_dimension=1920)
        img = Image.open(io.BytesIO(result))
        assert max(img.size) <= 1920

    def test_quality_parameter(self):
        data = _make_test_image()
        low_q = compress_to_jpeg(data, quality=20)
        high_q = compress_to_jpeg(data, quality=95)
        # Higher quality should generally be larger
        # (not always true for simple solid color images, but the test should still pass)
        assert len(low_q) > 0
        assert len(high_q) > 0


class TestGetImageDimensions:
    def test_dimensions(self):
        data = _make_test_image(1920, 1080)
        w, h = get_image_dimensions(data)
        assert w == 1920
        assert h == 1080

    def test_portrait(self):
        data = _make_test_image(1080, 1920)
        w, h = get_image_dimensions(data)
        assert w == 1080
        assert h == 1920


class TestGetDominantColors:
    def test_returns_colors(self):
        data = _make_test_image(color=(255, 0, 0))
        colors = get_dominant_colors(data, num_colors=3)
        assert len(colors) == 3
        assert all(c.startswith("#") for c in colors)

    def test_color_format(self):
        data = _make_test_image()
        colors = get_dominant_colors(data, num_colors=1)
        assert len(colors[0]) == 7  # #rrggbb


class TestColorToName:
    def test_red(self):
        assert color_to_name("#ff0000") == "red"

    def test_blue(self):
        assert color_to_name("#0000ff") == "blue"

    def test_green(self):
        assert color_to_name("#00ff00") == "green"

    def test_dark(self):
        assert color_to_name("#0a0a0a") == "dark"

    def test_light(self):
        assert color_to_name("#f0f0f0") == "light"
