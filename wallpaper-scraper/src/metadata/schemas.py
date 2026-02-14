"""Pydantic models mapping exactly to Baserow table 810 fields."""
from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class WallpaperRow(BaseModel):
    """Maps directly to Baserow table 810 fields."""

    wallpaperTitle: str = Field(description="AI-generated title")
    Width: int = Field(description="Original pixel width")
    Height: int = Field(description="Original pixel height")
    imgUrl: str = Field(description="Source image URL")
    Alt_Text: str = Field(description="AI-generated alt text")
    Artist_text: str = Field(default="", description="Artist name")
    Artist_link: str = Field(default="", description="Artist URL")
    IsMobile: bool = Field(description="True if portrait")
    IsReported: bool = Field(default=False, description="Always false")
    IsVip: bool = Field(default=False, description="Always false")
    OrgUploadDate: str = Field(description="YYYY-MM-DD format date")
    CategoryTags: str = Field(description="AI-generated comma-separated tags")
    imageFile: list = Field(
        default_factory=list,
        description='[{"name": "baserow_internal_filename.jpg"}]',
    )
    imgHash: str = Field(description="Perceptual hash")

    def to_baserow_dict(self) -> dict:
        """Convert to dict with exact Baserow field names (including spaces)."""
        return {
            "wallpaperTitle": self.wallpaperTitle,
            "Width": self.Width,
            "Height": self.Height,
            "imgUrl": self.imgUrl,
            "Alt Text": self.Alt_Text,
            "Artist text": self.Artist_text,
            "Artist link": self.Artist_link,
            "IsMobile": self.IsMobile,
            "IsReported": self.IsReported,
            "IsVip": self.IsVip,
            "OrgUploadDate": self.OrgUploadDate,
            "CategoryTags": self.CategoryTags,
            "imageFile": self.imageFile,
            "imgHash": self.imgHash,
        }


class ScrapedImageInfo(BaseModel):
    """Information extracted from a page about a wallpaper image."""

    image_url: str = Field(description="Direct URL to the full-resolution image")
    page_url: str = Field(description="URL of the page the image was found on")
    artist_name: str = Field(default="", description="Artist/photographer name")
    artist_link: str = Field(default="", description="Link to artist profile")
    upload_date: Optional[str] = Field(
        default=None, description="Original upload date (YYYY-MM-DD)"
    )
    page_tags: list[str] = Field(
        default_factory=list, description="Tags found on the page"
    )
    score: float = Field(
        default=0.0, description="Confidence score for this being a wallpaper"
    )
    width: Optional[int] = Field(
        default=None, description="Width if known from page metadata"
    )
    height: Optional[int] = Field(
        default=None, description="Height if known from page metadata"
    )


class ScrapeRequest(BaseModel):
    """Request to scrape wallpapers from URLs."""

    urls: list[str] = Field(description="URLs to scrape")
    max_pages: int = Field(default=5, ge=1, le=100, description="Max pages per URL")
    min_width: Optional[int] = Field(default=None, description="Override min width")
    min_height: Optional[int] = Field(default=None, description="Override min height")
    jpeg_quality: Optional[int] = Field(
        default=None, ge=1, le=100, description="Override JPEG quality"
    )
