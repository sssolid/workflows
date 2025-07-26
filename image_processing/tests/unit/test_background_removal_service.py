# ===== tests/unit/test_background_removal_service.py =====
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from PIL import Image
import io

from src.services.background_removal_service import BackgroundRemovalService
from src.models.file_models import ProcessedFile, FileMetadata, FileType
from src.models.processing_models import BackgroundRemovalRequest, ProcessingModel


class TestBackgroundRemovalService:
    """Test BackgroundRemovalService."""

    @pytest.fixture
    def bg_service(self):
        """Create BackgroundRemovalService for testing."""
        with patch('src.services.background_removal_service.settings'), \
                patch('src.services.background_removal_service.ensure_directory'):
            return BackgroundRemovalService()

    @pytest.fixture
    def mock_file(self):
        """Create mock ProcessedFile for testing."""
        metadata = FileMetadata(
            file_id="test_123",
            original_path=Path("/test/image.jpg"),
            filename="image.jpg",
            file_type=FileType.JPEG,
            size_bytes=1024,
            checksum_md5="test",
            checksum_sha256="test",
            modified_at=datetime.now()
        )

        file_obj = ProcessedFile(metadata=metadata)
        file_obj.current_location = Path("/test/image.jpg")
        return file_obj

    def test_remove_background_success(self, bg_service, mock_file):
        """Test successful background removal."""
        request = BackgroundRemovalRequest(
            file_id="test_123",
            model=ProcessingModel.ISNET_GENERAL
        )

        # Mock image processing
        mock_img = Mock(spec=Image.Image)
        mock_img.width = 1000
        mock_img.height = 1000
        mock_img.convert.return_value = mock_img

        mock_result_img = Mock(spec=Image.Image)
        mock_result_img.width = 800
        mock_result_img.height = 800
        mock_result_img.split.return_value = [None, None, None, Mock()]

        with patch('builtins.open'), \
                patch('src.services.background_removal_service.Image.open', return_value=mock_img), \
                patch.object(bg_service, '_get_model_session'), \
                patch('src.services.background_removal_service.remove') as mock_remove, \
                patch('src.services.background_removal_service.Image.open', return_value=mock_result_img), \
                patch.object(bg_service, '_post_process_result', return_value=mock_result_img), \
                patch.object(bg_service, '_crop_to_content', return_value=mock_result_img), \
                patch.object(bg_service, '_calculate_quality_score', return_value=85.0):
            mock_remove.return_value = b"fake_image_data"

            result = bg_service.remove_background(mock_file, request)

            assert result.success is True
            assert result.quality_score == 85.0
            assert result.model_used == ProcessingModel.ISNET_GENERAL.value

    def test_remove_background_file_not_found(self, bg_service, mock_file):
        """Test background removal with missing file."""
        mock_file.current_location = Path("/nonexistent/file.jpg")

        request = BackgroundRemovalRequest(
            file_id="test_123",
            model=ProcessingModel.ISNET_GENERAL
        )

        result = bg_service.remove_background(mock_file, request)

        assert result.success is False
        assert "not found" in result.error_message.lower()