# ===== tests/unit/test_file_models.py =====
import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, mock_open

from src.models.file_models import (
    FileMetadata, FileStatus, FileType, ImageDimensions, ProcessedFile
)


class TestFileMetadata:
    """Test FileMetadata model."""

    def test_file_metadata_creation(self):
        """Test creating a valid FileMetadata instance."""
        metadata = FileMetadata(
            file_id="test123_abcd5678",
            original_path=Path("/test/image.jpg"),
            filename="image.jpg",
            file_type=FileType.JPEG,
            size_bytes=1024000,
            checksum_md5="d41d8cd98f00b204e9800998ecf8427e",
            checksum_sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            modified_at=datetime.now()
        )

        assert metadata.file_id == "test123_abcd5678"
        assert metadata.filename == "image.jpg"
        assert metadata.size_mb == 1.0
        assert metadata.stem == "image"
        assert metadata.is_psd is False

    def test_file_metadata_validation(self):
        """Test FileMetadata validation."""
        with pytest.raises(ValueError, match="file_id must be at least 10 characters"):
            FileMetadata(
                file_id="short",
                original_path=Path("/test/image.jpg"),
                filename="image.jpg",
                file_type=FileType.JPEG,
                size_bytes=1024,
                checksum_md5="test",
                checksum_sha256="test",
                modified_at=datetime.now()
            )


class TestImageDimensions:
    """Test ImageDimensions model."""

    def test_image_dimensions_properties(self):
        """Test ImageDimensions calculated properties."""
        dims = ImageDimensions(width=3000, height=2000)

        assert dims.aspect_ratio == 1.5
        assert dims.megapixels == 6.0
        assert dims.is_high_resolution is True

    def test_low_resolution_detection(self):
        """Test low resolution detection."""
        dims = ImageDimensions(width=1000, height=800)

        assert dims.is_high_resolution is False


class TestProcessedFile:
    """Test ProcessedFile model."""

    def test_add_processing_step(self):
        """Test adding processing steps."""
        metadata = FileMetadata(
            file_id="test123_abcd5678",
            original_path=Path("/test/image.jpg"),
            filename="image.jpg",
            file_type=FileType.JPEG,
            size_bytes=1024,
            checksum_md5="test",
            checksum_sha256="test",
            modified_at=datetime.now()
        )

        file_obj = ProcessedFile(metadata=metadata)
        file_obj.add_processing_step("background_removal", {"model": "isnet"})

        assert len(file_obj.processing_history) == 1
        assert file_obj.processing_history[0]["step"] == "background_removal"
        assert file_obj.processing_history[0]["details"]["model"] == "isnet"

    def test_update_status(self):
        """Test status updates."""
        metadata = FileMetadata(
            file_id="test123_abcd5678",
            original_path=Path("/test/image.jpg"),
            filename="image.jpg",
            file_type=FileType.JPEG,
            size_bytes=1024,
            checksum_md5="test",
            checksum_sha256="test",
            modified_at=datetime.now()
        )

        file_obj = ProcessedFile(metadata=metadata)
        file_obj.update_status(FileStatus.PROCESSING, "Started processing")

        assert file_obj.metadata.status == FileStatus.PROCESSING
        assert len(file_obj.processing_history) == 1
        assert file_obj.processing_history[0]["details"]["reason"] == "Started processing"