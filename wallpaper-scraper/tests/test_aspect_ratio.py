"""Tests for aspect ratio utilities."""
import pytest

from src.utils.aspect_ratio import (
    calculate_aspect_ratio,
    classify_aspect_ratio,
    get_minimum_resolution,
    is_mobile,
    meets_minimum_resolution,
)


class TestCalculateAspectRatio:
    def test_16_9(self):
        assert calculate_aspect_ratio(1920, 1080) == (16, 9)

    def test_4_3(self):
        assert calculate_aspect_ratio(1600, 1200) == (4, 3)

    def test_1_1(self):
        assert calculate_aspect_ratio(1080, 1080) == (1, 1)

    def test_3840x2160(self):
        assert calculate_aspect_ratio(3840, 2160) == (16, 9)

    def test_invalid_zero(self):
        with pytest.raises(ValueError):
            calculate_aspect_ratio(0, 1080)

    def test_invalid_negative(self):
        with pytest.raises(ValueError):
            calculate_aspect_ratio(-1920, 1080)


class TestClassifyAspectRatio:
    def test_16_9_exact(self):
        assert classify_aspect_ratio(1920, 1080) == "16:9"

    def test_16_9_4k(self):
        assert classify_aspect_ratio(3840, 2160) == "16:9"

    def test_9_16(self):
        assert classify_aspect_ratio(1080, 1920) == "9:16"

    def test_21_9(self):
        assert classify_aspect_ratio(2560, 1080) == "21:9"

    def test_4_3(self):
        assert classify_aspect_ratio(1600, 1200) == "4:3"

    def test_3_2(self):
        assert classify_aspect_ratio(1920, 1280) == "3:2"

    def test_1_1(self):
        assert classify_aspect_ratio(1080, 1080) == "1:1"

    def test_32_9(self):
        assert classify_aspect_ratio(3840, 1080) == "32:9"

    def test_tolerance_16_9(self):
        # 1920x1082 is within 2% of 16:9
        assert classify_aspect_ratio(1920, 1082) == "16:9"

    def test_unknown_ratio(self):
        # Something weird
        result = classify_aspect_ratio(1000, 700)
        assert ":" in result  # Should return simplified ratio


class TestIsMobile:
    def test_landscape(self):
        assert is_mobile(1920, 1080) is False

    def test_portrait(self):
        assert is_mobile(1080, 1920) is True

    def test_square(self):
        assert is_mobile(1080, 1080) is False


class TestMeetsMinimumResolution:
    def test_16_9_meets(self):
        assert meets_minimum_resolution(1920, 1080) is True

    def test_16_9_exceeds(self):
        assert meets_minimum_resolution(3840, 2160) is True

    def test_16_9_below(self):
        assert meets_minimum_resolution(1280, 720) is False

    def test_9_16_meets(self):
        assert meets_minimum_resolution(1080, 1920) is True

    def test_9_16_below(self):
        assert meets_minimum_resolution(720, 1280) is False

    def test_1_1_meets(self):
        assert meets_minimum_resolution(1080, 1080) is True

    def test_1_1_below(self):
        assert meets_minimum_resolution(800, 800) is False

    def test_21_9_meets(self):
        assert meets_minimum_resolution(2560, 1080) is True


class TestGetMinimumResolution:
    def test_16_9(self):
        assert get_minimum_resolution(1920, 1080) == (1920, 1080)

    def test_9_16(self):
        assert get_minimum_resolution(1080, 1920) == (1080, 1920)

    def test_unknown(self):
        # Should return default
        w, h = get_minimum_resolution(1000, 700)
        assert w == 1920 and h == 1080
