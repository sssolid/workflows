# ===== tests/integration/test_workflow_integration.py =====
import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from src.workflows.file_monitoring import FileMonitoringWorkflow


class TestWorkflowIntegration:
    """Integration tests for n8n workflows."""

    @pytest.fixture
    def temp_dirs(self):
        """Create temporary directories for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_dir = temp_path / "input"
            metadata_dir = temp_path / "metadata"

            input_dir.mkdir()
            metadata_dir.mkdir()

            yield {
                "input": input_dir,
                "metadata": metadata_dir
            }

    def test_scan_workflow_integration(self, temp_dirs):
        """Test the complete scan workflow."""
        # Create a test file
        test_file = temp_dirs["input"] / "test_image.jpg"
        test_file.write_bytes(b"fake image data" * 100)  # Create file with some size

        with patch('src.workflows.file_monitoring.settings') as mock_settings:
            mock_settings.processing.input_dir = temp_dirs["input"]
            mock_settings.processing.metadata_dir = temp_dirs["metadata"]
            mock_settings.processing.min_file_size_bytes = 100

            workflow = FileMonitoringWorkflow()

            # Mock file validation to return True
            with patch('src.services.file_monitor_service.is_valid_image_file', return_value=True), \
                    patch('src.services.file_monitor_service.detect_file_type'), \
                    patch('src.services.file_monitor_service.calculate_file_checksums',
                          return_value=("md5hash", "sha256hash")):
                result = workflow.scan_for_new_files()

        assert result["success"] is True
        assert result["new_files_count"] >= 0
        assert "new_files" in result