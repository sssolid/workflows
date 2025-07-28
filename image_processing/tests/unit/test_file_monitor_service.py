# ===== tests/unit/test_file_monitor_service.py =====
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from datetime import datetime

from ...src.services.file_monitor_service import FileMonitorService
from ...src.models.file_models import FileStatus, FileType


class TestFileMonitorService:
    """Test FileMonitorService."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings for testing."""
        with patch('src.services.file_monitor_service.settings') as mock_settings:
            mock_settings.processing.input_dir = Path("/test/input")
            mock_settings.processing.metadata_dir = Path("/test/metadata")
            mock_settings.processing.min_file_size_bytes = 1024
            mock_settings.processing.processing_timeout_seconds = 300
            yield mock_settings

    @pytest.fixture
    def file_monitor(self, mock_settings):
        """Create FileMonitorService instance for testing."""
        with patch('src.services.file_monitor_service.ensure_directory'), \
                patch.object(FileMonitorService, '_load_state'):
            return FileMonitorService()

    def test_discover_new_files(self, file_monitor):
        """Test discovering new files."""
        # Mock file system
        mock_file = Mock()
        mock_file.name = "test.jpg"
        mock_file.is_file.return_value = True
        mock_file.stat.return_value = Mock(st_size=2048, st_mtime=datetime.now().timestamp())
        mock_file.suffix = ".jpg"

        with patch.object(file_monitor.input_dir, 'exists', return_value=True), \
                patch.object(file_monitor.input_dir, 'iterdir', return_value=[mock_file]), \
                patch('src.services.file_monitor_service.is_valid_image_file', return_value=True), \
                patch.object(file_monitor, '_create_file_metadata') as mock_create, \
                patch.object(file_monitor, '_save_state'):
            # Mock file metadata creation
            mock_processed_file = Mock()
            mock_processed_file.metadata.file_id = "test_123"
            mock_create.return_value = mock_processed_file

            # Test discovery
            new_files = file_monitor.discover_new_files()

            assert len(new_files) == 1
            assert new_files[0] == mock_processed_file
            assert mock_processed_file.metadata.file_id in file_monitor._tracked_files

    def test_get_files_needing_processing(self, file_monitor):
        """Test getting files that need processing."""
        # Setup mock files
        mock_file1 = Mock()
        mock_file1.metadata.status = FileStatus.DISCOVERED
        mock_file2 = Mock()
        mock_file2.metadata.status = FileStatus.FAILED
        mock_file3 = Mock()
        mock_file3.metadata.status = FileStatus.APPROVED

        file_monitor._tracked_files = {
            "file1": mock_file1,
            "file2": mock_file2,
            "file3": mock_file3
        }

        processable = file_monitor.get_files_needing_processing()

        assert len(processable) == 2  # DISCOVERED and FAILED
        assert mock_file1 in processable
        assert mock_file2 in processable
        assert mock_file3 not in processable

    def test_update_file_status(self, file_monitor):
        """Test updating file status."""
        mock_file = Mock()
        file_monitor._tracked_files = {"test_id": mock_file}

        with patch.object(file_monitor, '_save_state'):
            result = file_monitor.update_file_status(
                "test_id",
                FileStatus.PROCESSING,
                "Starting processing"
            )

        assert result is True
        mock_file.update_status.assert_called_once_with(
            FileStatus.PROCESSING,
            "Starting processing"
        )