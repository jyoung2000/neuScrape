"""Aspect ratio calculation and classification utilities."""
from math import gcd

# Known aspect ratios with their minimum resolutions
KNOWN_RATIOS = {
    (16, 9): {"name": "16:9", "min_w": 1920, "min_h": 1080},
    (9, 16): {"name": "9:16", "min_w": 1080, "min_h": 1920},
    (21, 9): {"name": "21:9", "min_w": 2560, "min_h": 1080},
    (4, 3): {"name": "4:3", "min_w": 1600, "min_h": 1200},
    (3, 4): {"name": "3:4", "min_w": 1200, "min_h": 1600},
    (3, 2): {"name": "3:2", "min_w": 1920, "min_h": 1280},
    (2, 3): {"name": "2:3", "min_w": 1280, "min_h": 1920},
    (1, 1): {"name": "1:1", "min_w": 1080, "min_h": 1080},
    (32, 9): {"name": "32:9", "min_w": 3840, "min_h": 1080},
}


def calculate_aspect_ratio(width: int, height: int) -> tuple[int, int]:
    """Calculate simplified aspect ratio using GCD."""
    if width <= 0 or height <= 0:
        raise ValueError(f"Invalid dimensions: {width}x{height}")
    divisor = gcd(width, height)
    return (width // divisor, height // divisor)


def classify_aspect_ratio(width: int, height: int, tolerance: float = 0.02) -> str:
    """Classify dimensions into a known aspect ratio name with tolerance.

    Returns the ratio string (e.g. "16:9") or "other" if no match.
    """
    if width <= 0 or height <= 0:
        raise ValueError(f"Invalid dimensions: {width}x{height}")

    actual_ratio = width / height

    for (rw, rh), info in KNOWN_RATIOS.items():
        expected_ratio = rw / rh
        if abs(actual_ratio - expected_ratio) / expected_ratio <= tolerance:
            return info["name"]

    # No known match — return simplified ratio
    simplified = calculate_aspect_ratio(width, height)
    return f"{simplified[0]}:{simplified[1]}"


def is_mobile(width: int, height: int) -> bool:
    """Return True if the image is portrait (height > width)."""
    return height > width


def meets_minimum_resolution(
    width: int,
    height: int,
    min_w: int = 1920,
    min_h: int = 1080,
) -> bool:
    """Check if dimensions meet minimum resolution requirements.

    Uses the minimum for the classified aspect ratio if known,
    otherwise falls back to the provided min_w/min_h.
    """
    ratio_name = classify_aspect_ratio(width, height)

    for (_rw, _rh), info in KNOWN_RATIOS.items():
        if info["name"] == ratio_name:
            return width >= info["min_w"] and height >= info["min_h"]

    # Unknown ratio — use generic minimums
    return width >= min_w and height >= min_h


def get_minimum_resolution(width: int, height: int) -> tuple[int, int]:
    """Get the minimum resolution for the classified aspect ratio."""
    ratio_name = classify_aspect_ratio(width, height)

    for (_rw, _rh), info in KNOWN_RATIOS.items():
        if info["name"] == ratio_name:
            return (info["min_w"], info["min_h"])

    return (1920, 1080)
