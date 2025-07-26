# ===== src/services/file_monitor_service.py =====
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from ..config.settings import settings
from ..models.file_models import FileMetadata, FileStatus, FileType, ProcessedFile
from ..utils.crypto_utils import calculate_file_checksums, generate_file_id
from ..utils.error_handling import handle_processing_errors
from ..utils.filesystem_utils import is_valid_image_file, detect_file_type, ensure_directory

logger = logging.getLogger(__name__)


class FileMonitorService:
    """
    Service for monitoring files and tracking their processing state.

    This service is responsible for:
    - Discovering new files in the input directory
    - Tracking file state across the processing pipeline
    - Preventing duplicate processing based on checksums
    - Recovering from system failures by re-checking incomplete files
    - Integrating with part mapping for automatic part number detection
    """

    def __init__(self):
        self.input_dir = settings.processing.input_dir
        self.metadata_dir = settings.processing.metadata_dir
        self.state_file = self.metadata_dir / "file_monitor_state.json"

        ensure_directory(self.metadata_dir)
        self._tracked_files: Dict[str, ProcessedFile] = {}
        self._load_state()

    def _load_state(self) -> None:
        """Load previously tracked files from state file."""
        try:
            if self.state_file.exists():
                with open(self.state_file, 'r') as f:
                    state_data = json.load(f)

                for file_data in state_data.get('tracked_files', []):
                    try:
                        # Handle both old and new file data formats
                        if 'metadata' in file_data:
                            processed_file = ProcessedFile.parse_obj(file_data)
                        else:
                            # Legacy format conversion
                            metadata = FileMetadata(**file_data)
                            processed_file = ProcessedFile(metadata=metadata)

                        self._tracked_files[processed_file.metadata.file_id] = processed_file
                    except Exception as e:
                        logger.warning(f"Skipping invalid file data: {e}")
                        continue

                logger.info(f"Loaded {len(self._tracked_files)} tracked files from state")
            else:
                logger.info("No previous state found, starting fresh")
        except Exception as e:
            logger.error(f"Error loading state file: {e}")
            self._tracked_files = {}

    def _save_state(self) -> None:
        """Save current tracked files to state file."""
        try:
            state_data = {
                'tracked_files': [file.dict() for file in self._tracked_files.values()],
                'last_saved': datetime.now().isoformat(),
                'total_files': len(self._tracked_files)
            }

            with open(self.state_file, 'w') as f:
                json.dump(state_data, f, indent=2, default=str)

            logger.debug(f"Saved state with {len(self._tracked_files)} files")
        except Exception as e:
            logger.error(f"Error saving state file: {e}")

    @handle_processing_errors("file_discovery")
    def discover_new_files(self) -> List[ProcessedFile]:
        """
        Discover new files in the input directory.

        Returns:
            List of newly discovered files
        """
        if not self.input_dir.exists():
            logger.warning(f"Input directory does not exist: {self.input_dir}")
            return []

        discovered_files = []

        for file_path in self.input_dir.iterdir():
            if not is_valid_image_file(file_path, settings.processing.min_file_size_bytes):
                continue

            try:
                processed_file = self._create_file_metadata(file_path)

                # Check if we've already seen this file (by checksum)
                existing_file = self.get_file_by_checksum(processed_file.metadata.checksum_sha256)

                if not existing_file:
                    self._tracked_files[processed_file.metadata.file_id] = processed_file
                    discovered_files.append(processed_file)
                    logger.info(f"Discovered new file: {file_path.name} (ID: {processed_file.metadata.file_id})")
                else:
                    logger.debug(f"File already tracked by checksum: {file_path.name}")

            except Exception as e:
                logger.error(f"Error processing file {file_path}: {e}")
                continue

        if discovered_files:
            self._save_state()

        return discovered_files

    def _create_file_metadata(self, file_path: Path) -> ProcessedFile:
        """Create file metadata for a discovered file."""
        file_stats = file_path.stat()
        file_type = detect_file_type(file_path)

        # Calculate checksums
        md5_hash, sha256_hash = calculate_file_checksums(file_path)
        file_id = generate_file_id(file_path, sha256_hash)

        metadata = FileMetadata(
            file_id=file_id,
            original_path=file_path,
            filename=file_path.name,
            file_type=file_type,
            size_bytes=file_stats.st_size,
            checksum_md5=md5_hash,
            checksum_sha256=sha256_hash,
            modified_at=datetime.fromtimestamp(file_stats.st_mtime),
            status=FileStatus.DISCOVERED
        )

        processed_file = ProcessedFile(
            metadata=metadata,
            current_location=file_path
        )

        # Add discovery step to history
        processed_file.add_processing_step("file_discovered", {
            "path": str(file_path),
            "size_bytes": file_stats.st_size,
            "file_type": file_type.value if file_type else "unknown"
        })

        return processed_file

    def get_files_by_status(self, status: FileStatus) -> List[ProcessedFile]:
        """Get all files with a specific status."""
        return [
            file for file in self._tracked_files.values()
            if file.metadata.status == status
        ]

    def get_files_needing_processing(self) -> List[ProcessedFile]:
        """
        Get files that need processing, including failed/incomplete ones.

        This is the key method that ensures no files are left in limbo.
        """
        processable_statuses = {
            FileStatus.DISCOVERED,
            FileStatus.QUEUED,
            FileStatus.FAILED
        }

        return [
            file for file in self._tracked_files.values()
            if file.metadata.status in processable_statuses
        ]

    def update_file_status(
            self,
            file_id: str,
            new_status: FileStatus,
            reason: Optional[str] = None,
            new_location: Optional[Path] = None
    ) -> bool:
        """
        Update the status of a tracked file.

        Args:
            file_id: File identifier
            new_status: New status to set
            reason: Optional reason for status change
            new_location: Optional new file location

        Returns:
            True if update was successful
        """
        if file_id not in self._tracked_files:
            logger.warning(f"Attempted to update unknown file: {file_id}")
            return False

        file_obj = self._tracked_files[file_id]
        file_obj.update_status(new_status, reason)

        if new_location:
            file_obj.current_location = new_location

        self._save_state()
        logger.info(f"Updated file {file_id} status to {new_status}")
        return True

    def get_file_by_id(self, file_id: str) -> Optional[ProcessedFile]:
        """Get a file by its ID."""
        return self._tracked_files.get(file_id)

    def get_file_by_checksum(self, checksum: str) -> Optional[ProcessedFile]:
        """Find a file by its checksum (for duplicate detection)."""
        for file_obj in self._tracked_files.values():
            if file_obj.metadata.checksum_sha256 == checksum:
                return file_obj
        return None

    def scan_and_recover_incomplete(self) -> List[ProcessedFile]:
        """
        Scan for incomplete processing and mark files for retry.

        This method helps recover from system failures by identifying
        files that should be processed but are in an incomplete state.
        """
        recovered_files = []

        for file_obj in self._tracked_files.values():
            if file_obj.metadata.status == FileStatus.PROCESSING:
                # Check if file has been processing for too long
                last_update = file_obj.metadata.created_at
                if file_obj.processing_history:
                    last_step_time = max(
                        datetime.fromisoformat(step.get('timestamp', '1970-01-01T00:00:00'))
                        for step in file_obj.processing_history
                    )
                    last_update = max(last_update, last_step_time)

                time_since_update = datetime.now() - last_update
                if time_since_update.total_seconds() > settings.processing.processing_timeout_seconds:
                    file_obj.update_status(
                        FileStatus.FAILED,
                        f"Processing timeout after {time_since_update.total_seconds()}s"
                    )
                    recovered_files.append(file_obj)
                    logger.warning(f"Marked file {file_obj.metadata.file_id} as failed due to timeout")

        if recovered_files:
            self._save_state()

        return recovered_files

    def add_file_part_number(self, file_id: str, part_number: str, confidence: float = 1.0) -> bool:
        """
        Add part number to a tracked file.

        Args:
            file_id: File identifier
            part_number: Part number to assign
            confidence: Confidence in the mapping (0.0 to 1.0)

        Returns:
            True if successful
        """
        if file_id not in self._tracked_files:
            return False

        file_obj = self._tracked_files[file_id]
        file_obj.part_number = part_number.upper().strip()

        file_obj.add_processing_step("part_number_mapped", {
            "part_number": part_number,
            "confidence": confidence,
            "source": "automatic_mapping"
        })

        self._save_state()
        return True

    def get_statistics(self) -> Dict[str, int]:
        """Get file processing statistics."""
        stats = {}
        for status in FileStatus:
            stats[status.value] = len(self.get_files_by_status(status))

        stats['total'] = len(self._tracked_files)
        return stats

    def reset_state(self) -> None:
        """Reset all tracking state (for debugging/maintenance)."""
        self._tracked_files.clear()
        if self.state_file.exists():
            self.state_file.unlink()
        logger.warning("File monitor state has been reset")