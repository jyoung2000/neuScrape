"""FastAPI route handlers for the wallpaper scraper API."""
import asyncio
from typing import Optional

from fastapi import APIRouter, HTTPException

from src.api.models import (
    HealthResponse,
    JobListResponse,
    JobProgress,
    JobStatus,
    ScrapeRequestBody,
    ScrapeResponse,
    StatsResponse,
)

router = APIRouter()

# These are set during app startup (see main.py)
_job_queue = None
_scraper_engine = None
_captioner = None
_browser = None


def set_dependencies(job_queue, scraper_engine, captioner, browser):
    """Inject dependencies from app startup."""
    global _job_queue, _scraper_engine, _captioner, _browser
    _job_queue = job_queue
    _scraper_engine = scraper_engine
    _captioner = captioner
    _browser = browser


@router.post("/scrape", response_model=ScrapeResponse)
async def scrape(request: ScrapeRequestBody):
    """Submit a scrape job for one or more URLs."""
    if not _job_queue or not _scraper_engine:
        raise HTTPException(status_code=503, detail="Service not ready")

    if not request.urls:
        raise HTTPException(status_code=400, detail="No URLs provided")

    if not _job_queue.can_start_new:
        raise HTTPException(
            status_code=429,
            detail="Maximum concurrent jobs reached. Wait for current jobs to finish.",
        )

    # Create job
    job = _job_queue.create_job(
        urls=request.urls,
        max_pages=request.max_pages,
    )

    # Start the scrape task
    task = asyncio.create_task(
        _scraper_engine.run_job(
            job_id=job.id,
            urls=request.urls,
            max_pages=request.max_pages,
            min_width=request.min_width,
            min_height=request.min_height,
            jpeg_quality=request.jpeg_quality,
        )
    )
    _job_queue.register_task(job.id, task)

    return ScrapeResponse(
        job_id=job.id,
        status=job.status,
        urls=request.urls,
    )


@router.get("/jobs", response_model=JobListResponse)
async def list_jobs():
    """List all jobs and their status."""
    if not _job_queue:
        raise HTTPException(status_code=503, detail="Service not ready")

    return JobListResponse(jobs=_job_queue.list_jobs())


@router.get("/jobs/{job_id}", response_model=JobProgress)
async def get_job(job_id: str):
    """Get detailed progress for a specific job."""
    if not _job_queue:
        raise HTTPException(status_code=503, detail="Service not ready")

    job = _job_queue.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return job


@router.delete("/jobs/{job_id}")
async def cancel_job(job_id: str):
    """Cancel a running or queued job."""
    if not _job_queue:
        raise HTTPException(status_code=503, detail="Service not ready")

    if _job_queue.cancel_job(job_id):
        return {"status": "cancelled", "job_id": job_id}
    else:
        raise HTTPException(
            status_code=400, detail="Job cannot be cancelled (already completed or not found)"
        )


@router.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    ai_model = _captioner.model_type if _captioner and _captioner.is_loaded else "loading"
    browser_status = "ready" if _browser and _browser.is_ready else "not_ready"

    return HealthResponse(
        status="ok",
        version="1.0.0",
        ai_model=ai_model,
        browser=browser_status,
    )


@router.get("/stats", response_model=StatsResponse)
async def stats():
    """Get scraping statistics."""
    if not _job_queue:
        raise HTTPException(status_code=503, detail="Service not ready")

    s = _job_queue.stats
    return StatsResponse(**s)
