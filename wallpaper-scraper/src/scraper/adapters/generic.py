"""Universal wallpaper scraping adapter — works on ANY wallpaper website."""
import asyncio
import re
from datetime import date
from typing import AsyncGenerator, Optional
from urllib.parse import urljoin, urlparse

from playwright.async_api import Page

from src.metadata.extractor import extract_artist, extract_tags, extract_upload_date
from src.metadata.schemas import ScrapedImageInfo
from src.scraper.adapters.base import BaseAdapter
from src.scraper.browser import BrowserManager
from src.scraper.discovery import (
    extract_srcset_urls,
    is_image_url,
    is_thumbnail,
    resolve_full_image_url,
    score_image_url,
    should_skip_url,
)
from src.utils.logging import get_logger
from src.utils.rate_limiter import RateLimiter

logger = get_logger("generic-adapter")

# Minimum score threshold to consider an image as a wallpaper candidate
MIN_SCORE_THRESHOLD = 40.0

# Patterns in link hrefs that suggest the link leads to a wallpaper detail page
DETAIL_PAGE_PATTERNS = [
    r"/wallpaper/",
    r"/photo/",
    r"/image/",
    r"/view/",
    r"/detail/",
    r"/full/",
    r"/w/",
    r"/p/",
]

# Next page link patterns
NEXT_PAGE_SELECTORS = [
    "a[rel='next']",
    "a.next",
    "a.pagination-next",
    "[class*='next'] a",
    "[class*='pagination'] a:last-child",
    "a[aria-label='Next']",
    "a[aria-label='Next page']",
    "a:has-text('Next')",
    "a:has-text('next')",
    "a:has-text('>')",
    "a:has-text('»')",
    "button:has-text('Next')",
    "button:has-text('Load more')",
    "button:has-text('Load More')",
    "button:has-text('Show more')",
    "[class*='load-more']",
    "[class*='loadmore']",
]


class GenericAdapter(BaseAdapter):
    """Universal adapter that scrapes wallpapers from any website.

    Uses heuristic scoring to identify wallpaper images on any page,
    follows detail pages and download links, and handles pagination.
    """

    def __init__(
        self,
        browser: BrowserManager,
        rate_limiter: Optional[RateLimiter] = None,
        request_delay: float = 2.0,
    ):
        super().__init__(browser)
        self.rate_limiter = rate_limiter or RateLimiter(delay_seconds=request_delay)
        self._seen_urls: set[str] = set()

    async def can_handle(self, url: str) -> bool:
        """Generic adapter handles all URLs."""
        return True

    async def scrape(
        self, url: str, max_pages: int = 5
    ) -> AsyncGenerator[ScrapedImageInfo, None]:
        """Scrape wallpapers from any URL. Yields ScrapedImageInfo objects."""
        context = await self.browser.new_context()
        try:
            page = await self.browser.new_page(context)
            current_url = url
            pages_scraped = 0

            while current_url and pages_scraped < max_pages:
                logger.info(
                    "Scraping page %d/%d: %s", pages_scraped + 1, max_pages, current_url
                )
                await self.rate_limiter.wait()

                try:
                    await self.browser.load_page(current_url, page=page)
                except Exception as e:
                    logger.error("Failed to load page %s: %s", current_url, e)
                    break

                # Scroll to trigger lazy loading
                await self.browser.scroll_page(page, max_scrolls=5)

                # Discover images on this page
                candidates = await self._discover_images(page, current_url)
                logger.info("Found %d image candidates on page", len(candidates))

                # Check if this is a listing page (many images) or detail page (one main image)
                if len(candidates) > 3:
                    # Listing page — find detail page links and follow them
                    detail_links = await self._find_detail_links(page, current_url)

                    if detail_links:
                        logger.info(
                            "Found %d detail page links, following them",
                            len(detail_links),
                        )
                        for detail_url in detail_links:
                            if detail_url in self._seen_urls:
                                continue
                            self._seen_urls.add(detail_url)

                            detail_images = await self._scrape_detail_page(
                                context, detail_url
                            )
                            for img in detail_images:
                                yield img
                    else:
                        # No detail pages — yield the candidates directly
                        for candidate in candidates:
                            if candidate.image_url not in self._seen_urls:
                                self._seen_urls.add(candidate.image_url)
                                yield candidate
                else:
                    # Detail page or page with few images — yield directly
                    for candidate in candidates:
                        if candidate.image_url not in self._seen_urls:
                            self._seen_urls.add(candidate.image_url)
                            yield candidate

                # Find next page
                pages_scraped += 1
                if pages_scraped < max_pages:
                    next_url = await self._find_next_page(page, current_url)
                    if next_url and next_url != current_url:
                        current_url = next_url
                    else:
                        break
                else:
                    break

        finally:
            await context.close()

    async def _discover_images(
        self, page: Page, page_url: str
    ) -> list[ScrapedImageInfo]:
        """Find all wallpaper image candidates on the current page."""
        candidates: list[ScrapedImageInfo] = []
        seen_urls: set[str] = set()

        page_html = await page.content()
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(page_html, "lxml")

        # Extract page-level metadata
        artist_name, artist_link = extract_artist(soup, page_url)
        upload_date = extract_upload_date(soup)
        page_tags = extract_tags(soup)

        # 1. Find images via <img> tags
        img_elements = await page.query_selector_all("img")
        for img in img_elements:
            urls_to_check = []

            # Check various source attributes
            for attr in ["src", "data-src", "data-original", "data-full", "data-href",
                         "data-lazy-src", "data-srcset"]:
                val = await img.get_attribute(attr)
                if val and not val.startswith("data:"):
                    if attr in ("data-srcset", "srcset"):
                        srcset_urls = extract_srcset_urls(val, page_url)
                        if srcset_urls:
                            urls_to_check.append(
                                (srcset_urls[0][0], {"is_srcset_max": True})
                            )
                    else:
                        urls_to_check.append((urljoin(page_url, val), {}))

            # Check srcset
            srcset = await img.get_attribute("srcset")
            if srcset:
                srcset_urls = extract_srcset_urls(srcset, page_url)
                if srcset_urls:
                    urls_to_check.append(
                        (srcset_urls[0][0], {"is_srcset_max": True})
                    )

            # Get dimensions and alt text
            width = await img.get_attribute("width")
            height = await img.get_attribute("height")
            alt = await img.get_attribute("alt") or ""

            for url, extra_ctx in urls_to_check:
                if url in seen_urls or should_skip_url(url):
                    continue

                ctx = {
                    "width": width,
                    "height": height,
                    "alt_text": alt,
                    **extra_ctx,
                }
                score = score_image_url(url, ctx)
                if score >= MIN_SCORE_THRESHOLD:
                    seen_urls.add(url)
                    # If this looks like a thumbnail, try to find full version
                    if is_thumbnail(url):
                        full_url = resolve_full_image_url(url, page_url)
                        if full_url != url:
                            url = full_url

                    candidates.append(
                        ScrapedImageInfo(
                            image_url=url,
                            page_url=page_url,
                            artist_name=artist_name,
                            artist_link=artist_link,
                            upload_date=upload_date or date.today().isoformat(),
                            page_tags=page_tags,
                            score=score,
                            width=int(width) if width and width.isdigit() else None,
                            height=int(height) if height and height.isdigit() else None,
                        )
                    )

        # 2. Find images via <a> tags with image links
        link_elements = await page.query_selector_all("a[href]")
        for link in link_elements:
            href = await link.get_attribute("href")
            if not href:
                continue
            full_url = urljoin(page_url, href)

            if is_image_url(full_url) and full_url not in seen_urls:
                link_text = await link.inner_text()
                ctx = {"link_text": link_text.strip() if link_text else ""}
                score = score_image_url(full_url, ctx)

                if score >= MIN_SCORE_THRESHOLD:
                    seen_urls.add(full_url)
                    candidates.append(
                        ScrapedImageInfo(
                            image_url=full_url,
                            page_url=page_url,
                            artist_name=artist_name,
                            artist_link=artist_link,
                            upload_date=upload_date or date.today().isoformat(),
                            page_tags=page_tags,
                            score=score,
                        )
                    )

        # 3. Check <picture>/<source> tags
        source_elements = await page.query_selector_all("picture source, source[srcset]")
        for source in source_elements:
            srcset = await source.get_attribute("srcset")
            if srcset:
                srcset_urls = extract_srcset_urls(srcset, page_url)
                if srcset_urls:
                    url = srcset_urls[0][0]
                    if url not in seen_urls and not should_skip_url(url):
                        seen_urls.add(url)
                        score = score_image_url(url, {"is_srcset_max": True})
                        if score >= MIN_SCORE_THRESHOLD:
                            candidates.append(
                                ScrapedImageInfo(
                                    image_url=url,
                                    page_url=page_url,
                                    artist_name=artist_name,
                                    artist_link=artist_link,
                                    upload_date=upload_date or date.today().isoformat(),
                                    page_tags=page_tags,
                                    score=score,
                                )
                            )

        # 4. Check og:image and twitter:image meta tags
        for meta_prop in ["og:image", "twitter:image", "twitter:image:src"]:
            meta = soup.find("meta", attrs={"property": meta_prop}) or soup.find(
                "meta", attrs={"name": meta_prop}
            )
            if meta and meta.get("content"):
                url = urljoin(page_url, meta["content"])
                if url not in seen_urls and not should_skip_url(url):
                    seen_urls.add(url)
                    score = score_image_url(url, {"in_main_content": True})
                    if score >= MIN_SCORE_THRESHOLD:
                        candidates.append(
                            ScrapedImageInfo(
                                image_url=url,
                                page_url=page_url,
                                artist_name=artist_name,
                                artist_link=artist_link,
                                upload_date=upload_date or date.today().isoformat(),
                                page_tags=page_tags,
                                score=score,
                            )
                        )

        # Sort by score descending
        candidates.sort(key=lambda c: c.score, reverse=True)
        return candidates

    async def _find_detail_links(
        self, page: Page, page_url: str
    ) -> list[str]:
        """Find links that lead to wallpaper detail/view pages."""
        detail_links: list[str] = []
        domain = urlparse(page_url).netloc

        link_elements = await page.query_selector_all("a[href]")
        for link in link_elements:
            href = await link.get_attribute("href")
            if not href:
                continue

            full_url = urljoin(page_url, href)
            parsed = urlparse(full_url)

            # Must be same domain
            if parsed.netloc != domain:
                continue

            # Check if link looks like a detail page
            path = parsed.path.lower()
            is_detail = any(pat in path for pat in [
                "/wallpaper/", "/photo/", "/image/", "/view/",
                "/detail/", "/full/", "/w/", "/p/",
            ])

            if not is_detail:
                # Check if the link wraps an image (common gallery pattern)
                child_img = await link.query_selector("img")
                if child_img:
                    # Link wrapping an image on the same domain — likely detail page
                    if not is_image_url(full_url):
                        is_detail = True

            if is_detail and full_url not in detail_links:
                detail_links.append(full_url)

        return detail_links

    async def _scrape_detail_page(
        self, context, detail_url: str
    ) -> list[ScrapedImageInfo]:
        """Scrape a single detail/view page for wallpaper images."""
        page = await self.browser.new_page(context)
        try:
            await self.rate_limiter.wait()
            await self.browser.load_page(detail_url, page=page)

            candidates = await self._discover_images(page, detail_url)

            # On detail pages, also look for download buttons
            download_urls = await self._find_download_links(page, detail_url)
            for url in download_urls:
                if url not in {c.image_url for c in candidates}:
                    page_html = await page.content()
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(page_html, "lxml")
                    artist_name, artist_link = extract_artist(soup, detail_url)
                    upload_date = extract_upload_date(soup)
                    page_tags = extract_tags(soup)

                    candidates.append(
                        ScrapedImageInfo(
                            image_url=url,
                            page_url=detail_url,
                            artist_name=artist_name,
                            artist_link=artist_link,
                            upload_date=upload_date or date.today().isoformat(),
                            page_tags=page_tags,
                            score=80.0,
                        )
                    )

            # Return only the highest-scoring candidate from detail pages
            if candidates:
                candidates.sort(key=lambda c: c.score, reverse=True)
                return [candidates[0]]
            return []

        except Exception as e:
            logger.warning("Failed to scrape detail page %s: %s", detail_url, e)
            return []
        finally:
            await page.close()

    async def _find_download_links(self, page: Page, page_url: str) -> list[str]:
        """Find download button/link URLs on a detail page."""
        download_urls: list[str] = []

        selectors = [
            "a[download]",
            "a[href*='download']",
            "a[class*='download']",
            "a[id*='download']",
            "button[class*='download']",
            "a:has-text('Download')",
            "a:has-text('download')",
            "a:has-text('Full Size')",
            "a:has-text('Original')",
            "a:has-text('Full Resolution')",
        ]

        for selector in selectors:
            try:
                elements = await page.query_selector_all(selector)
                for el in elements:
                    href = await el.get_attribute("href")
                    if href:
                        full_url = urljoin(page_url, href)
                        if is_image_url(full_url) and full_url not in download_urls:
                            download_urls.append(full_url)
            except Exception:
                continue

        return download_urls

    async def _find_next_page(self, page: Page, current_url: str) -> Optional[str]:
        """Find the URL of the next page."""
        for selector in NEXT_PAGE_SELECTORS:
            try:
                el = page.locator(selector).first
                if await el.is_visible(timeout=1000):
                    href = await el.get_attribute("href")
                    if href:
                        next_url = urljoin(current_url, href)
                        if next_url != current_url:
                            logger.debug("Found next page: %s", next_url)
                            return next_url

                    # If it's a button without href (load more), try clicking
                    tag = await el.evaluate("el => el.tagName.toLowerCase()")
                    if tag == "button":
                        await el.click()
                        await asyncio.sleep(2)
                        # Page content updated in place
                        return current_url + "#loaded"  # Signal to re-scrape
            except Exception:
                continue

        # Try URL pattern-based pagination
        next_url = self._guess_next_page_url(current_url)
        return next_url

    def _guess_next_page_url(self, url: str) -> Optional[str]:
        """Try to guess the next page URL from patterns."""
        parsed = urlparse(url)
        path = parsed.path
        query = parsed.query

        # Pattern: ?page=N
        page_match = re.search(r"[?&]page=(\d+)", url)
        if page_match:
            current_page = int(page_match.group(1))
            return url.replace(
                f"page={current_page}", f"page={current_page + 1}"
            )

        # Pattern: /page/N/
        path_match = re.search(r"/page/(\d+)/?", path)
        if path_match:
            current_page = int(path_match.group(1))
            return url.replace(
                f"/page/{current_page}", f"/page/{current_page + 1}"
            )

        # Pattern: ?offset=N or ?start=N
        for param in ["offset", "start"]:
            match = re.search(rf"[?&]{param}=(\d+)", url)
            if match:
                current_val = int(match.group(1))
                # Guess page size of 20 or 24
                next_val = current_val + 24
                return url.replace(
                    f"{param}={current_val}", f"{param}={next_val}"
                )

        # Pattern: ?p=N
        p_match = re.search(r"[?&]p=(\d+)", url)
        if p_match:
            current_page = int(p_match.group(1))
            return url.replace(f"p={current_page}", f"p={current_page + 1}")

        return None
