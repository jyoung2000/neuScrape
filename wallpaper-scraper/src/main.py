"""FastAPI application — wallpaper scraper web API on port 1629."""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.ai.captioner import WallpaperCaptioner
from src.api.jobs import JobQueue
from src.api.routes import router, set_dependencies
from src.downloader.manager import DownloadManager
from src.scraper.browser import BrowserManager
from src.scraper.engine import ScraperEngine
from src.storage.baserow import BaserowClient
from src.utils.logging import setup_logging

logger = setup_logging()

# Global instances
browser: BrowserManager = None
captioner: WallpaperCaptioner = None
baserow: BaserowClient = None
job_queue: JobQueue = None
engine: ScraperEngine = None
downloader: DownloadManager = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown."""
    global browser, captioner, baserow, job_queue, engine, downloader

    logger.info("Starting wallpaper scraper...")

    # Initialize components
    browser = BrowserManager(
        headless=os.environ.get("HEADLESS", "true").lower() == "true",
        proxy=os.environ.get("HTTP_PROXY"),
    )
    await browser.start()

    captioner = WallpaperCaptioner(
        model_name=os.environ.get("AI_MODEL", "auto")
    )
    # Load AI model in background to not block startup
    import asyncio
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, captioner.load)

    baserow = BaserowClient(
        api_url=os.environ.get("BASEROW_API_URL", "https://baserow.jymedia.cc"),
        api_token=os.environ.get("BASEROW_API_TOKEN", ""),
        table_id=int(os.environ.get("BASEROW_TABLE_ID", "810")),
    )

    downloader = DownloadManager(
        max_concurrent=int(os.environ.get("MAX_CONCURRENT_DOWNLOADS", "5")),
    )

    job_queue = JobQueue(
        max_concurrent=int(os.environ.get("MAX_CONCURRENT_JOBS", "2"))
    )
    job_queue.load()  # Recover from restart

    engine = ScraperEngine(
        browser=browser,
        captioner=captioner,
        baserow=baserow,
        job_queue=job_queue,
        download_manager=downloader,
        request_delay=float(os.environ.get("REQUEST_DELAY", "2")),
        jpeg_quality=int(os.environ.get("JPEG_QUALITY", "85")),
        min_width=int(os.environ.get("MIN_WIDTH", "1920")),
        min_height=int(os.environ.get("MIN_HEIGHT", "1080")),
    )

    # Wire up route dependencies
    set_dependencies(job_queue, engine, captioner, browser)

    logger.info("Wallpaper scraper ready on port %s", os.environ.get("API_PORT", "1629"))
    yield

    # Shutdown
    logger.info("Shutting down...")
    await browser.stop()
    await downloader.close()
    await baserow.close()


app = FastAPI(
    title="Wallpaper Scraper",
    description="Universal wallpaper scraping service with AI captioning",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(router)
