"""Extract metadata (artist, date, tags) from wallpaper pages."""
import re
from datetime import date, datetime
from typing import Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from src.utils.logging import get_logger

logger = get_logger("metadata")

# Common patterns for artist/photographer credits
ARTIST_PATTERNS = [
    r"(?:photo(?:graph)?(?:er|y)?|artist|creator|author|by|uploaded by|shot by)\s*[:\-]?\s*(.+)",
]

# CSS selectors likely to contain artist info
ARTIST_SELECTORS = [
    "[class*='artist']",
    "[class*='author']",
    "[class*='photographer']",
    "[class*='creator']",
    "[class*='uploader']",
    "[class*='user-name']",
    "[class*='username']",
    "[rel='author']",
    ".byline",
    ".credit",
]

# CSS selectors likely to contain dates
DATE_SELECTORS = [
    "time[datetime]",
    "[class*='date']",
    "[class*='time']",
    "[class*='published']",
    "[class*='uploaded']",
    "meta[property='article:published_time']",
    "meta[name='date']",
]

# CSS selectors likely to contain tags
TAG_SELECTORS = [
    "[class*='tag'] a",
    "[class*='tags'] a",
    "[class*='category'] a",
    "[class*='keyword'] a",
    "[rel='tag']",
    ".tag",
    ".chip",
    ".label",
]


def extract_artist(soup: BeautifulSoup, page_url: str) -> tuple[str, str]:
    """Extract artist name and profile link from page.

    Returns (artist_name, artist_link) tuple.
    """
    # Try CSS selectors first
    for selector in ARTIST_SELECTORS:
        elements = soup.select(selector)
        for el in elements:
            name = el.get_text(strip=True)
            if name and len(name) < 100:
                link = ""
                anchor = el if el.name == "a" else el.find("a")
                if anchor and anchor.get("href"):
                    link = urljoin(page_url, anchor["href"])
                return (name, link)

    # Try regex patterns on page text
    for pattern in ARTIST_PATTERNS:
        text_blocks = soup.find_all(string=re.compile(pattern, re.IGNORECASE))
        for text in text_blocks:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                if name and len(name) < 100:
                    parent = text.parent
                    link = ""
                    if parent:
                        anchor = (
                            parent if parent.name == "a" else parent.find("a")
                        )
                        if anchor and anchor.get("href"):
                            link = urljoin(page_url, anchor["href"])
                    return (name, link)

    return ("", "")


def extract_upload_date(soup: BeautifulSoup) -> Optional[str]:
    """Extract upload/publish date from page. Returns YYYY-MM-DD or None."""
    # Try <time datetime="..."> first
    time_el = soup.find("time", attrs={"datetime": True})
    if time_el:
        return _parse_date(time_el["datetime"])

    # Try meta tags
    for meta_name in [
        "article:published_time",
        "og:published_time",
        "datePublished",
        "date",
    ]:
        meta = soup.find("meta", attrs={"property": meta_name}) or soup.find(
            "meta", attrs={"name": meta_name}
        )
        if meta and meta.get("content"):
            parsed = _parse_date(meta["content"])
            if parsed:
                return parsed

    # Try date selectors
    for selector in DATE_SELECTORS:
        elements = soup.select(selector)
        for el in elements:
            dt_attr = el.get("datetime")
            if dt_attr:
                parsed = _parse_date(dt_attr)
                if parsed:
                    return parsed
            text = el.get_text(strip=True)
            if text:
                parsed = _parse_date(text)
                if parsed:
                    return parsed

    return None


def extract_tags(soup: BeautifulSoup) -> list[str]:
    """Extract tags/categories from page."""
    tags = set()

    for selector in TAG_SELECTORS:
        elements = soup.select(selector)
        for el in elements:
            tag_text = el.get_text(strip=True).lower()
            if tag_text and len(tag_text) < 50:
                # Clean up common prefixes
                tag_text = tag_text.lstrip("#")
                if tag_text:
                    tags.add(tag_text)

    # Also check meta keywords
    meta_kw = soup.find("meta", attrs={"name": "keywords"})
    if meta_kw and meta_kw.get("content"):
        for kw in meta_kw["content"].split(","):
            kw = kw.strip().lower()
            if kw:
                tags.add(kw)

    return list(tags)


def _parse_date(date_str: str) -> Optional[str]:
    """Try to parse a date string into YYYY-MM-DD format."""
    date_str = date_str.strip()

    formats = [
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
        "%B %d, %Y",
        "%b %d, %Y",
        "%d %B %Y",
        "%d %b %Y",
        "%m/%d/%Y",
        "%d/%m/%Y",
        "%Y/%m/%d",
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue

    # Try dateutil as fallback
    try:
        from dateutil import parser as dateutil_parser

        dt = dateutil_parser.parse(date_str)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        pass

    return None
