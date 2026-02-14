"""Scraper engine — orchestrates the full wallpaper pipeline.

URL -> Discover -> Download -> Validate -> Compress -> AI Caption -> Dedup -> Upload
"""
import asyncio
import io
from datetime import date, datetime
from typing import Optional

from PIL import Image

from src.ai.captioner import WallpaperCaptioner
from src.api.jobs import JobQueue
from src.api.models import JobStatus
from src.downloader.compressor import compress_to_jpeg, get_image_dimensions
from src.downloader.dedup import DeduplicationChecker
from src.downloader.manager import DownloadManager
from src.downloader.validator import validate_image
from src.metadata.schemas import ScrapedImageInfo, WallpaperRow
from src.scraper.adapters.generic import GenericAdapter
from src.scraper.browser import BrowserManager
from src.storage.baserow import BaserowClient
from src.utils.logging import get_logger
from src.utils.rate_limiter import RateLimiter

logger = get_logger("engine")


class ScraperEngine:
    """Orchestrates the full wallpaper scraping pipeline."""

    def __init__(
        self,
        browser: BrowserManager,
        captioner: WallpaperCaptioner,
        baserow: BaserowClient,
        job_queue: JobQueue,
        download_manager: Optional[DownloadManager] = None,
        request_delay: float = 2.0,
        jpeg_quality: int = 85,
        min_width: int = 1920,
        min_height: int = 1080,
        dedup_enabled: bool = True,
        check_baserow_dedup: bool = True,
    ):
        self.browser = browser
        self.captioner = captioner
        self.baserow = baserow
        self.job_queue = job_queue
        self.downloader = download_manager or DownloadManager()
        self.rate_limiter = RateLimiter(delay_seconds=request_delay)
        self.jpeg_quality = jpeg_quality
        self.min_width = min_width
        self.min_height = min_height
        self.dedup_enabled = dedup_enabled
        self.check_baserow_dedup = check_baserow_dedup
        self._dedup = DeduplicationChecker()

    async def run_job(
        self,
        job_id: str,
        urls: list[str],
        max_pages: int = 5,
        min_width: Optional[int] = None,
        min_height: Optional[int] = None,
        jpeg_quality: Optional[int] = None,
    ) -> None:
        """Run a complete scrape job."""
        job = self.job_queue.get_job(job_id)
        if not job:
            logger.error("Job %s not found", job_id)
            return

        # Apply overrides
        effective_min_w = min_width or self.min_width
        effective_min_h = min_height or self.min_height
        effective_quality = jpeg_quality or self.jpeg_quality

        # Mark as running
        self.job_queue.update_job(
            job_id,
            status=JobStatus.RUNNING,
            started_at=datetime.utcnow().isoformat(),
        )

        try:
            adapter = GenericAdapter(
                browser=self.browser,
                rate_limiter=self.rate_limiter,
            )

            for url in urls:
                if job.status == JobStatus.CANCELLED:
                    break

                self.job_queue.update_job(job_id, current_url=url, current_page=0)
                logger.info("[Job %s] Scraping URL: %s", job_id, url)

                try:
                    async for image_info in adapter.scrape(url, max_pages=max_pages):
                        if job.status == JobStatus.CANCELLED:
                            break

                        job.total_found += 1
                        self.job_queue.update_job(
                            job_id, total_found=job.total_found
                        )

                        await self._process_image(
                            job_id=job_id,
                            image_info=image_info,
                            min_width=effective_min_w,
                            min_height=effective_min_h,
                            jpeg_quality=effective_quality,
                        )

                except asyncio.CancelledError:
                    logger.info("[Job %s] Cancelled", job_id)
                    break
                except Exception as e:
                    error_msg = f"Error scraping {url}: {e}"
                    logger.error("[Job %s] %s", job_id, error_msg)
                    self.job_queue.add_error(job_id, error_msg)
                    self.job_queue.record_error(job_id)

            # Mark completed
            final_status = (
                JobStatus.CANCELLED
                if job.status == JobStatus.CANCELLED
                else JobStatus.COMPLETED
            )
            self.job_queue.update_job(
                job_id,
                status=final_status,
                completed_at=datetime.utcnow().isoformat(),
            )
            logger.info(
                "[Job %s] Finished: found=%d, downloaded=%d, uploaded=%d, dupes=%d",
                job_id,
                job.total_found,
                job.downloaded,
                job.uploaded,
                job.duplicates_skipped,
            )

        except asyncio.CancelledError:
            self.job_queue.update_job(
                job_id,
                status=JobStatus.CANCELLED,
                completed_at=datetime.utcnow().isoformat(),
            )
        except Exception as e:
            logger.error("[Job %s] Fatal error: %s", job_id, e)
            self.job_queue.update_job(
                job_id,
                status=JobStatus.FAILED,
                completed_at=datetime.utcnow().isoformat(),
            )
            self.job_queue.add_error(job_id, f"Fatal: {e}")

    async def _process_image(
        self,
        job_id: str,
        image_info: ScrapedImageInfo,
        min_width: int,
        min_height: int,
        jpeg_quality: int,
    ) -> None:
        """Process a single discovered image through the full pipeline."""
        url = image_info.image_url

        try:
            # Step 1: Download
            logger.debug("Downloading: %s", url)
            image_data = await self.downloader.download(url)
            if not image_data:
                self.job_queue.add_error(job_id, f"Download failed: {url}")
                return

            job = self.job_queue.get_job(job_id)
            if job:
                job.downloaded += 1

            # Step 2: Validate
            validation = validate_image(image_data, min_width, min_height)
            if not validation.valid:
                logger.debug("Validation failed for %s: %s", url, validation.error)
                return

            # Step 3: Dedup — check session + Baserow
            if self.dedup_enabled:
                # Check session
                dup_url = self._dedup.is_duplicate_in_session(validation.phash)
                if dup_url:
                    logger.debug("Session duplicate: %s matches %s", url, dup_url)
                    self.job_queue.record_duplicate(job_id)
                    return

                # Check Baserow
                if self.check_baserow_dedup and self.baserow.is_configured:
                    try:
                        if await self.baserow.check_hash_exists(validation.phash):
                            logger.debug("Baserow duplicate: %s", url)
                            self.job_queue.record_duplicate(job_id)
                            self._dedup.add_hash(validation.phash, url)
                            return
                    except Exception as e:
                        logger.warning("Baserow dedup check failed: %s", e)

                self._dedup.add_hash(validation.phash, url)

            # Step 4: JPEG Compression
            jpeg_bytes = compress_to_jpeg(image_data, quality=jpeg_quality)

            # Step 5: AI Captioning
            try:
                img = Image.open(io.BytesIO(image_data))
                if img.mode != "RGB":
                    img = img.convert("RGB")
                ai_result = self.captioner.generate_all(img)
            except Exception as e:
                logger.warning("AI captioning failed for %s: %s", url, e)
                ai_result = {
                    "title": "Untitled Wallpaper",
                    "alt_text": "A wallpaper image.",
                    "tags": "wallpaper, background, hd",
                }

            # Step 6: Build metadata
            upload_date = image_info.upload_date or date.today().isoformat()
            metadata = WallpaperRow(
                wallpaperTitle=ai_result["title"],
                Width=validation.width,
                Height=validation.height,
                imgUrl=url,
                Alt_Text=ai_result["alt_text"],
                Artist_text=image_info.artist_name,
                Artist_link=image_info.artist_link,
                IsMobile=validation.is_mobile,
                IsReported=False,
                IsVip=False,
                OrgUploadDate=upload_date,
                CategoryTags=ai_result["tags"],
                imgHash=validation.phash,
            )

            # Step 7: Upload to Baserow
            if self.baserow.is_configured:
                try:
                    result = await self.baserow.upload_wallpaper(jpeg_bytes, metadata)
                    self.job_queue.record_upload(job_id, validation.aspect_ratio)
                    logger.info(
                        "Uploaded: %s (%dx%d, %s)",
                        ai_result["title"],
                        validation.width,
                        validation.height,
                        validation.aspect_ratio,
                    )
                except Exception as e:
                    error_msg = f"Baserow upload failed for {url}: {e}"
                    logger.error(error_msg)
                    self.job_queue.add_error(job_id, error_msg)
                    self.job_queue.record_error(job_id)
            else:
                logger.warning("Baserow not configured — skipping upload for %s", url)

        except Exception as e:
            error_msg = f"Pipeline error for {url}: {e}"
            logger.error(error_msg)
            self.job_queue.add_error(job_id, error_msg)
            self.job_queue.record_error(job_id)
