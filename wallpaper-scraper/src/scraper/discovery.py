"""Image link detection and scoring for wallpaper discovery."""
import re
from typing import Optional
from urllib.parse import urljoin, urlparse

from src.utils.logging import get_logger

logger = get_logger("discovery")

# URL patterns that indicate high-res/full-size images
HIGH_RES_URL_PATTERNS = [
    r"original",
    r"full",
    r"raw",
    r"download",
    r"[_-]4k",
    r"[_-]uhd",
    r"[_-]hd",
    r"\d{3,4}x\d{3,4}",
    r"w=\d{4}",
    r"width=\d{4}",
    r"3840",
    r"2560",
    r"1920",
]

# URL patterns that indicate thumbnails/small images (negative signals)
THUMBNAIL_PATTERNS = [
    r"/thumb(?:s|nail)?[s/]",
    r"/small/",
    r"/tiny/",
    r"/preview/",
    r"/crop/",
    r"[_-](?:thumb|small|tiny|xs|sm|mini|icon)",
    r"\?.*(?:w|width)=(?:[1-9]\d?|[1-3]\d{2})\b",  # width < 400
    r"\?.*(?:h|height)=(?:[1-9]\d?|[1-3]\d{2})\b",
    r"/(?:avatar|logo|icon|badge|favicon)",
]

# Image file extensions
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif"}

# Link text that suggests download/full-size
DOWNLOAD_LINK_TEXT = {
    "download",
    "full size",
    "full resolution",
    "original",
    "original size",
    "hd",
    "4k",
    "uhd",
    "high resolution",
    "full image",
    "view full",
    "save",
    "get wallpaper",
    "download wallpaper",
}

# Elements to skip (ads, tracking, UI elements)
SKIP_PATTERNS = [
    r"google",
    r"facebook",
    r"twitter",
    r"analytics",
    r"tracking",
    r"pixel",
    r"beacon",
    r"ad[sv]?[/.]",
    r"doubleclick",
    r"syndication",
    r"\.gif$",  # usually tracking pixels or animations
    r"\.svg$",  # usually icons
    r"data:image",
    r"base64",
    r"1x1",
    r"spacer",
    r"blank",
    r"placeholder",
]


def is_image_url(url: str) -> bool:
    """Check if URL points to an image file."""
    parsed = urlparse(url.split("?")[0].split("#")[0])
    path = parsed.path.lower()
    return any(path.endswith(ext) for ext in IMAGE_EXTENSIONS)


def should_skip_url(url: str) -> bool:
    """Check if URL should be skipped (ads, tracking, etc.)."""
    url_lower = url.lower()
    return any(re.search(pat, url_lower) for pat in SKIP_PATTERNS)


def is_thumbnail(url: str) -> bool:
    """Check if URL looks like a thumbnail."""
    url_lower = url.lower()
    return any(re.search(pat, url_lower) for pat in THUMBNAIL_PATTERNS)


def score_image_url(url: str, context: Optional[dict] = None) -> float:
    """Score an image URL for likelihood of being a high-res wallpaper.

    Higher score = more likely to be a wallpaper. Range: 0-100.

    Context dict can include:
      - link_text: text of the link/button
      - alt_text: alt attribute of the image
      - in_main_content: whether the image is in main content area
      - width: known width from attributes
      - height: known height from attributes
      - is_srcset_max: whether this is the largest srcset variant
    """
    context = context or {}
    score = 50.0  # base score

    url_lower = url.lower()

    # Skip signals (immediate reject)
    if should_skip_url(url):
        return 0.0

    # Negative: thumbnail patterns
    if is_thumbnail(url):
        score -= 30

    # Positive: high-res URL patterns
    for pattern in HIGH_RES_URL_PATTERNS:
        if re.search(pattern, url_lower):
            score += 10
            break

    # Positive: known dimensions in URL
    dim_match = re.search(r"(\d{3,5})x(\d{3,5})", url_lower)
    if dim_match:
        w, h = int(dim_match.group(1)), int(dim_match.group(2))
        if w >= 1920 or h >= 1920:
            score += 20
        elif w >= 1280 or h >= 1280:
            score += 10

    # Positive: known dimensions from attributes
    width = context.get("width")
    height = context.get("height")
    if width and height:
        try:
            w, h = int(width), int(height)
            if w >= 1920 or h >= 1920:
                score += 25
            elif w >= 1280 or h >= 1280:
                score += 10
            elif w < 400 and h < 400:
                score -= 30
        except (ValueError, TypeError):
            pass

    # Positive: download/full-size link text
    link_text = context.get("link_text", "").lower().strip()
    if link_text and any(kw in link_text for kw in DOWNLOAD_LINK_TEXT):
        score += 15

    # Positive: largest srcset variant
    if context.get("is_srcset_max"):
        score += 15

    # Positive: in main content area
    if context.get("in_main_content"):
        score += 5

    # Positive: image extension
    if is_image_url(url):
        score += 5

    return max(0.0, min(100.0, score))


def extract_srcset_urls(srcset: str, base_url: str) -> list[tuple[str, int]]:
    """Parse srcset attribute and return [(url, width)] sorted by width descending."""
    results = []
    for part in srcset.split(","):
        part = part.strip()
        if not part:
            continue
        pieces = part.split()
        if len(pieces) >= 2:
            url = urljoin(base_url, pieces[0])
            descriptor = pieces[-1]
            # Parse width descriptor (e.g., "1920w")
            width_match = re.match(r"(\d+)w", descriptor)
            if width_match:
                results.append((url, int(width_match.group(1))))
            else:
                # Pixel density descriptor (e.g., "2x")
                density_match = re.match(r"([\d.]+)x", descriptor)
                density = float(density_match.group(1)) if density_match else 1.0
                results.append((url, int(density * 1920)))
        elif len(pieces) == 1:
            results.append((urljoin(base_url, pieces[0]), 0))

    results.sort(key=lambda x: x[1], reverse=True)
    return results


def resolve_full_image_url(thumb_url: str, page_url: str) -> str:
    """Attempt to convert a thumbnail URL to a full-size URL by pattern manipulation."""
    # Common thumb → full patterns
    replacements = [
        (r"/thumbs?/", "/full/"),
        (r"/small/", "/full/"),
        (r"/preview/", "/original/"),
        (r"/crop/", "/original/"),
        (r"[_-]thumb\.", "."),
        (r"[_-]small\.", "."),
        (r"[_-](?:sm|xs|mini)\.", "."),
        (r"\?w=\d+&?", "?"),
        (r"\?width=\d+&?", "?"),
        (r"&w=\d+", ""),
        (r"&width=\d+", ""),
    ]

    result = thumb_url
    for pattern, replacement in replacements:
        new_result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        if new_result != result:
            result = new_result
            break

    # Clean up trailing ? or &
    result = re.sub(r"[?&]$", "", result)
    return result
