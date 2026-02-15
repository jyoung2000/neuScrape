"""Pydantic models for API request/response schemas."""
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    """Job lifecycle states."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ScrapeRequestBody(BaseModel):
    """POST /scrape request body."""

    urls: list[str] = Field(description="URLs to scrape for wallpapers")
    max_pages: int = Field(default=5, ge=1, le=100, description="Max pages to scrape per URL")
    min_width: Optional[int] = Field(default=None, description="Override minimum width")
    min_height: Optional[int] = Field(default=None, description="Override minimum height")
    jpeg_quality: Optional[int] = Field(default=None, ge=1, le=100, description="Override JPEG quality")


class ScrapeResponse(BaseModel):
    """POST /scrape response."""

    job_id: str
    status: JobStatus
    urls: list[str]


class JobProgress(BaseModel):
    """Detailed job progress."""

    id: str
    status: JobStatus
    urls: list[str]
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    total_found: int = 0
    downloaded: int = 0
    uploaded: int = 0
    duplicates_skipped: int = 0
    errors: list[str] = Field(default_factory=list)
    current_url: Optional[str] = None
    current_page: int = 0


class JobListResponse(BaseModel):
    """GET /jobs response."""

    jobs: list[JobProgress]


class HealthResponse(BaseModel):
    """GET /health response."""

    status: str = "ok"
    version: str = "1.0.0"
    ai_model: Optional[str] = None
    browser: str = "unknown"


class StatsResponse(BaseModel):
    """GET /stats response."""

    total_scraped: int = 0
    total_uploaded: int = 0
    total_duplicates: int = 0
    total_errors: int = 0
    by_aspect_ratio: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)


class BaserowSettingsRequest(BaseModel):
    """PUT /settings/baserow request body."""

    api_url: Optional[str] = Field(default=None, description="Baserow API URL (e.g. https://baserow.jymedia.cc)")
    api_token: Optional[str] = Field(default=None, description="Baserow API token")
    table_id: Optional[int] = Field(default=None, ge=1, description="Baserow table ID")


class BaserowSettingsResponse(BaseModel):
    """GET /settings/baserow response."""

    api_url: str
    api_token_set: bool = Field(description="Whether an API token is configured (token value is not exposed)")
    table_id: int
    is_configured: bool = Field(description="Whether the client has a valid token")
