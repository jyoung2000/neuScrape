"""Image validation: dimensions, aspect ratio, corruption checks."""
import io
from dataclasses import dataclass
from typing import Optional

from PIL import Image

from src.utils.phash import phash as compute_phash

from src.utils.aspect_ratio import (
    classify_aspect_ratio,
    is_mobile,
    meets_minimum_resolution,
)
from src.utils.logging import get_logger

logger = get_logger("validator")


@dataclass
class ValidationResult:
    """Result of image validation."""

    valid: bool
    width: int = 0
    height: int = 0
    aspect_ratio: str = ""
    is_mobile: bool = False
    phash: str = ""
    error: Optional[str] = None


def validate_image(
    image_data: bytes,
    min_width: int = 1920,
    min_height: int = 1080,
    max_file_size_mb: int = 50,
) -> ValidationResult:
    """Validate an image for wallpaper suitability.

    Checks:
    1. Valid image format (Pillow can open)
    2. Not truncated/corrupt
    3. Meets minimum resolution for its aspect ratio
    4. File size within limits
    5. Generates perceptual hash
    """
    # Check file size
    size_mb = len(image_data) / (1024 * 1024)
    if size_mb > max_file_size_mb:
        return ValidationResult(
            valid=False, error=f"File too large: {size_mb:.1f}MB > {max_file_size_mb}MB"
        )

    # Try to open
    try:
        img = Image.open(io.BytesIO(image_data))
    except Exception as e:
        return ValidationResult(valid=False, error=f"Invalid image: {e}")

    # Verify not truncated
    try:
        img.load()
    except Exception as e:
        return ValidationResult(valid=False, error=f"Corrupt/truncated image: {e}")

    width, height = img.size

    # Check minimum dimensions
    if width < 800 or height < 600:
        return ValidationResult(
            valid=False,
            width=width,
            height=height,
            error=f"Too small: {width}x{height} (min 800x600)",
        )

    # Classify aspect ratio
    ratio = classify_aspect_ratio(width, height)
    mobile = is_mobile(width, height)

    # Check resolution for aspect ratio
    if not meets_minimum_resolution(width, height, min_width, min_height):
        return ValidationResult(
            valid=False,
            width=width,
            height=height,
            aspect_ratio=ratio,
            is_mobile=mobile,
            error=f"Below minimum resolution for {ratio}: {width}x{height}",
        )

    # Generate perceptual hash
    try:
        phash = str(compute_phash(img))
    except Exception as e:
        logger.warning("Failed to generate phash: %s", e)
        phash = ""

    return ValidationResult(
        valid=True,
        width=width,
        height=height,
        aspect_ratio=ratio,
        is_mobile=mobile,
        phash=phash,
    )
