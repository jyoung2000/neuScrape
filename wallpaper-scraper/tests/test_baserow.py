"""Tests for Baserow client and metadata schema."""
import pytest

from src.metadata.schemas import WallpaperRow


class TestWallpaperRow:
    def test_to_baserow_dict_field_names(self):
        """Verify exact field names match Baserow table 810."""
        row = WallpaperRow(
            wallpaperTitle="Golden Hour Mountain Lake",
            Width=3840,
            Height=2160,
            imgUrl="https://example.com/image.jpg",
            Alt_Text="A serene mountain lake at sunset",
            Artist_text="John Smith",
            Artist_link="https://example.com/john",
            IsMobile=False,
            IsReported=False,
            IsVip=False,
            OrgUploadDate="2024-06-15",
            CategoryTags="nature, landscape, mountains",
            imageFile=[{"name": "test.jpg"}],
            imgHash="f8e3a1b2c4d5e6f7",
        )

        d = row.to_baserow_dict()

        # Check exact field names (including spaces)
        assert "wallpaperTitle" in d
        assert "Width" in d
        assert "Height" in d
        assert "imgUrl" in d
        assert "Alt Text" in d  # Space in field name
        assert "Artist text" in d  # Space in field name
        assert "Artist link" in d  # Space in field name
        assert "IsMobile" in d
        assert "IsReported" in d
        assert "IsVip" in d
        assert "OrgUploadDate" in d
        assert "CategoryTags" in d
        assert "imageFile" in d
        assert "imgHash" in d

    def test_to_baserow_dict_values(self):
        row = WallpaperRow(
            wallpaperTitle="Test Title",
            Width=1920,
            Height=1080,
            imgUrl="https://example.com/img.jpg",
            Alt_Text="Test alt text",
            IsMobile=False,
            OrgUploadDate="2024-01-01",
            CategoryTags="test, tags",
            imgHash="abc123",
        )

        d = row.to_baserow_dict()

        assert d["wallpaperTitle"] == "Test Title"
        assert d["Width"] == 1920
        assert d["Height"] == 1080
        assert d["Alt Text"] == "Test alt text"
        assert d["IsMobile"] is False
        assert d["IsReported"] is False
        assert d["IsVip"] is False
        assert d["Artist text"] == ""
        assert d["Artist link"] == ""

    def test_defaults(self):
        row = WallpaperRow(
            wallpaperTitle="Test",
            Width=1920,
            Height=1080,
            imgUrl="https://example.com/img.jpg",
            Alt_Text="Alt",
            IsMobile=False,
            OrgUploadDate="2024-01-01",
            CategoryTags="tags",
            imgHash="hash",
        )

        assert row.IsReported is False
        assert row.IsVip is False
        assert row.Artist_text == ""
        assert row.Artist_link == ""
        assert row.imageFile == []

    def test_image_file_format(self):
        """Verify imageFile field format matches Baserow expectations."""
        row = WallpaperRow(
            wallpaperTitle="Test",
            Width=1920,
            Height=1080,
            imgUrl="https://example.com/img.jpg",
            Alt_Text="Alt",
            IsMobile=False,
            OrgUploadDate="2024-01-01",
            CategoryTags="tags",
            imageFile=[{"name": "VXotniBOVm8tbstZkKsMKbj2Qg7KmPvn_abc123.jpg"}],
            imgHash="hash",
        )

        d = row.to_baserow_dict()
        assert isinstance(d["imageFile"], list)
        assert len(d["imageFile"]) == 1
        assert "name" in d["imageFile"][0]


class TestBaserowClientConfig:
    def test_is_configured_with_token(self):
        from src.storage.baserow import BaserowClient

        client = BaserowClient(api_token="real_token_123")
        assert client.is_configured is True

    def test_not_configured_default(self):
        from src.storage.baserow import BaserowClient

        client = BaserowClient(api_token="your_token_here")
        assert client.is_configured is False

    def test_not_configured_empty(self):
        from src.storage.baserow import BaserowClient

        client = BaserowClient(api_token="")
        assert client.is_configured is False
