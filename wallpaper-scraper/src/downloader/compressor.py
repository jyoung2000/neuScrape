"""JPEG compression pipeline for wallpaper images."""
import io
from typing import Optional

from PIL import Image

from src.utils.logging import get_logger

logger = get_logger("compressor")


def compress_to_jpeg(
    image_data: bytes,
    quality: int = 85,
    max_dimension: Optional[int] = None,
) -> bytes:
    """Compress any image to JPEG format.

    Args:
        image_data: Raw image bytes (any format Pillow supports).
        quality: JPEG quality 1-100 (default 85).
        max_dimension: Optional max width/height (None = keep original resolution).

    Returns:
        JPEG bytes ready for upload.
    """
    img = Image.open(io.BytesIO(image_data))

    # Convert RGBA/palette to RGB (JPEG doesn't support transparency)
    if img.mode in ("RGBA", "LA"):
        background = Image.new("RGB", img.size, (0, 0, 0))
        background.paste(img, mask=img.split()[-1])
        img = background
    elif img.mode == "P":
        img = img.convert("RGBA")
        background = Image.new("RGB", img.size, (0, 0, 0))
        background.paste(img, mask=img.split()[-1])
        img = background
    elif img.mode != "RGB":
        img = img.convert("RGB")

    # Optional downscale (keep aspect ratio)
    if max_dimension and max(img.size) > max_dimension:
        img.thumbnail((max_dimension, max_dimension), Image.LANCZOS)

    # Compress to JPEG
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=quality, optimize=True, subsampling=0)
    jpeg_bytes = buffer.getvalue()

    logger.debug(
        "Compressed image: %d bytes -> %d bytes (quality=%d)",
        len(image_data),
        len(jpeg_bytes),
        quality,
    )
    return jpeg_bytes


def get_image_dimensions(image_data: bytes) -> tuple[int, int]:
    """Get (width, height) from image bytes without fully decoding."""
    img = Image.open(io.BytesIO(image_data))
    return img.size


def get_dominant_colors(image_data: bytes, num_colors: int = 5) -> list[str]:
    """Extract dominant colors as hex strings for AI fallback."""
    img = Image.open(io.BytesIO(image_data))
    if img.mode != "RGB":
        img = img.convert("RGB")

    # Resize for speed
    img = img.resize((100, 100), Image.LANCZOS)

    # Quantize to get dominant colors
    quantized = img.quantize(colors=num_colors, method=Image.Quantize.MEDIANCUT)
    palette = quantized.getpalette()

    colors = []
    palette_len = len(palette) // 3
    for i in range(min(num_colors, palette_len)):
        r, g, b = palette[i * 3 : i * 3 + 3]
        colors.append(f"#{r:02x}{g:02x}{b:02x}")

    # Pad if we got fewer colors than requested (e.g., solid color image)
    while len(colors) < num_colors and colors:
        colors.append(colors[-1])

    return colors


def color_to_name(hex_color: str) -> str:
    """Convert hex color to approximate color name."""
    r = int(hex_color[1:3], 16)
    g = int(hex_color[3:5], 16)
    b = int(hex_color[5:7], 16)

    # Simple color classification
    brightness = (r + g + b) / 3

    if brightness < 40:
        return "dark"
    if brightness > 220:
        return "light"

    if r > 180 and g < 100 and b < 100:
        return "red"
    if r < 100 and g > 180 and b < 100:
        return "green"
    if r < 100 and g < 100 and b > 180:
        return "blue"
    if r > 180 and g > 180 and b < 100:
        return "yellow"
    if r > 180 and g < 100 and b > 180:
        return "purple"
    if r < 100 and g > 180 and b > 180:
        return "cyan"
    if r > 180 and g > 100 and b < 100:
        return "orange"
    if r > 150 and g > 100 and b > 100 and abs(r - g) < 40:
        return "warm"
    if r < 100 and g < 100 and b < 150:
        return "cool"

    return "neutral"
