"""In-memory job queue with JSON persistence for restart recovery."""
import asyncio
import json
import os
import uuid
from datetime import datetime
from typing import Optional

from src.api.models import JobProgress, JobStatus
from src.utils.logging import get_logger

logger = get_logger("jobs")

JOBS_FILE = "/data/jobs.json"


class JobQueue:
    """In-memory job queue with disk persistence."""

    def __init__(self, max_concurrent: int = 2):
        self.max_concurrent = max_concurrent
        self._jobs: dict[str, JobProgress] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()
        self._stats = {
            "total_scraped": 0,
            "total_uploaded": 0,
            "total_duplicates": 0,
            "total_errors": 0,
            "by_aspect_ratio": {},
        }

    def create_job(self, urls: list[str], max_pages: int = 5, **kwargs) -> JobProgress:
        """Create a new job and return its progress object."""
        job_id = str(uuid.uuid4())[:8]
        job = JobProgress(
            id=job_id,
            status=JobStatus.QUEUED,
            urls=urls,
            created_at=datetime.utcnow().isoformat(),
        )
        self._jobs[job_id] = job
        self._save()
        logger.info("Created job %s for %d URLs", job_id, len(urls))
        return job

    def get_job(self, job_id: str) -> Optional[JobProgress]:
        """Get job progress by ID."""
        return self._jobs.get(job_id)

    def list_jobs(self) -> list[JobProgress]:
        """List all jobs."""
        return list(self._jobs.values())

    def update_job(self, job_id: str, **kwargs) -> Optional[JobProgress]:
        """Update job fields."""
        job = self._jobs.get(job_id)
        if not job:
            return None

        for key, value in kwargs.items():
            if hasattr(job, key):
                setattr(job, key, value)

        self._save()
        return job

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a running or queued job."""
        job = self._jobs.get(job_id)
        if not job:
            return False

        if job.status in (JobStatus.QUEUED, JobStatus.RUNNING):
            job.status = JobStatus.CANCELLED
            job.completed_at = datetime.utcnow().isoformat()

            # Cancel the asyncio task if running
            task = self._tasks.get(job_id)
            if task and not task.done():
                task.cancel()

            self._save()
            logger.info("Cancelled job %s", job_id)
            return True

        return False

    def register_task(self, job_id: str, task: asyncio.Task) -> None:
        """Register an asyncio task for a job."""
        self._tasks[job_id] = task

    def add_error(self, job_id: str, error: str) -> None:
        """Add an error message to a job."""
        job = self._jobs.get(job_id)
        if job:
            job.errors.append(error)
            if len(job.errors) > 100:
                job.errors = job.errors[-100:]  # Keep last 100 errors

    def record_upload(self, job_id: str, aspect_ratio: str = "") -> None:
        """Record a successful upload."""
        job = self._jobs.get(job_id)
        if job:
            job.uploaded += 1

        self._stats["total_uploaded"] += 1
        if aspect_ratio:
            self._stats["by_aspect_ratio"][aspect_ratio] = (
                self._stats["by_aspect_ratio"].get(aspect_ratio, 0) + 1
            )

    def record_duplicate(self, job_id: str) -> None:
        """Record a skipped duplicate."""
        job = self._jobs.get(job_id)
        if job:
            job.duplicates_skipped += 1
        self._stats["total_duplicates"] += 1

    def record_error(self, job_id: str) -> None:
        """Record an error in stats."""
        self._stats["total_errors"] += 1

    @property
    def running_count(self) -> int:
        """Number of currently running jobs."""
        return sum(
            1 for j in self._jobs.values() if j.status == JobStatus.RUNNING
        )

    @property
    def can_start_new(self) -> bool:
        """Whether a new job can start."""
        return self.running_count < self.max_concurrent

    @property
    def stats(self) -> dict:
        """Get aggregate stats."""
        by_status = {}
        for job in self._jobs.values():
            by_status[job.status.value] = by_status.get(job.status.value, 0) + 1

        return {
            **self._stats,
            "total_scraped": sum(j.total_found for j in self._jobs.values()),
            "by_status": by_status,
        }

    def _save(self) -> None:
        """Persist jobs to disk."""
        try:
            os.makedirs(os.path.dirname(JOBS_FILE), exist_ok=True)
            data = {
                jid: j.model_dump() for jid, j in self._jobs.items()
            }
            with open(JOBS_FILE, "w") as f:
                json.dump(data, f, default=str)
        except Exception as e:
            logger.warning("Failed to persist jobs: %s", e)

    def load(self) -> None:
        """Load jobs from disk (restart recovery)."""
        try:
            if os.path.exists(JOBS_FILE):
                with open(JOBS_FILE) as f:
                    data = json.load(f)

                for jid, jdata in data.items():
                    job = JobProgress(**jdata)
                    # Mark running jobs as failed (they didn't complete before restart)
                    if job.status == JobStatus.RUNNING:
                        job.status = JobStatus.FAILED
                        job.errors.append("Job interrupted by container restart")
                        job.completed_at = datetime.utcnow().isoformat()
                    self._jobs[jid] = job

                logger.info("Loaded %d jobs from disk", len(self._jobs))
        except Exception as e:
            logger.warning("Failed to load jobs from disk: %s", e)
