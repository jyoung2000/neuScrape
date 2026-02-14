"""Tests for AI captioner (unit tests that don't load the full model)."""
import io

import pytest
from PIL import Image

from src.ai.captioner import WallpaperCaptioner


def _make_test_image(width=1920, height=1080):
    """Create a simple test image."""
    img = Image.new("RGB", (width, height), (100, 150, 200))
    return img


class TestCaptionerPostProcessing:
    """Test the post-processing methods without loading models."""

    def setup_method(self):
        self.captioner = WallpaperCaptioner(model_name="blip")

    def test_clean_title_removes_prefix(self):
        result = self.captioner._clean_title("a wallpaper titled Mountain Sunrise")
        assert "a wallpaper titled" not in result.lower()
        assert result == "Mountain Sunrise"

    def test_clean_title_title_case(self):
        result = self.captioner._clean_title("mountain lake sunset")
        assert result == "Mountain Lake Sunset"

    def test_clean_title_max_words(self):
        result = self.captioner._clean_title(
            "a very long title that has way too many words in it for a wallpaper"
        )
        words = result.split()
        assert len(words) <= 8

    def test_clean_title_empty(self):
        result = self.captioner._clean_title("")
        assert result == "Untitled Wallpaper"

    def test_clean_alt_text_adds_period(self):
        result = self.captioner._clean_alt_text("A mountain scene with clouds")
        assert result.endswith(".")

    def test_clean_alt_text_capitalizes(self):
        result = self.captioner._clean_alt_text("a mountain scene")
        assert result[0].isupper()

    def test_clean_alt_text_limits_sentences(self):
        result = self.captioner._clean_alt_text(
            "First sentence. Second sentence. Third sentence. Fourth sentence."
        )
        sentences = result.split(". ")
        assert len(sentences) <= 3  # 2 sentences max, but split may vary

    def test_clean_tags_dedup(self):
        result = self.captioner._clean_tags("nature, nature, mountain, mountain, sky")
        tags = [t.strip() for t in result.split(",")]
        assert len(tags) == len(set(tags))  # No duplicates

    def test_clean_tags_lowercase(self):
        result = self.captioner._clean_tags("Nature, MOUNTAIN, Sky")
        tags = [t.strip() for t in result.split(",")]
        assert all(t == t.lower() for t in tags)

    def test_clean_tags_min_count(self):
        result = self.captioner._clean_tags("nature, sky")
        tags = [t.strip() for t in result.split(",")]
        assert len(tags) >= 5  # Should pad with generic tags

    def test_clean_tags_max_count(self):
        many_tags = ", ".join([f"tag{i}" for i in range(30)])
        result = self.captioner._clean_tags(many_tags)
        tags = [t.strip() for t in result.split(",")]
        assert len(tags) <= 20


class TestFallbacks:
    def setup_method(self):
        self.captioner = WallpaperCaptioner(model_name="blip")

    def test_fallback_title(self):
        img = _make_test_image()
        result = self.captioner._fallback_title(img)
        assert isinstance(result, str)
        assert len(result) > 0
        assert "Wallpaper" in result

    def test_fallback_tags(self):
        img = _make_test_image()
        result = self.captioner._fallback_tags(img)
        assert isinstance(result, str)
        assert "wallpaper" in result
        tags = [t.strip() for t in result.split(",")]
        assert len(tags) >= 5
