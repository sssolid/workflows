# ===== src/workflows/file_monitoring.py =====
"""
File Monitoring Workflow for n8n Integration.
Handles file discovery and part number mapping coordination.
"""

import json
import sys
import logging
from datetime import datetime
from typing import Dict, Any, List

from ..services.file_monitor_service import FileMonitorService
from ..services.part_mapping_service import PartMappingService
from ..services.notification_service import NotificationService
from ..models.file_models import FileStatus
from ..utils.logging_config import setup_logging

logger = logging.getLogger(__name__)


class FileMonitoringWorkflow:
    """File monitoring workflow integration for n8n."""

    def __init__(self):
        self.file_monitor = FileMonitorService()
        self.part_mapper = PartMappingService()
        self.notifier = NotificationService()

    def scan_for_new_files(self) -> Dict[str, Any]:
        """
        Scan for new files and perform initial part mapping.
        Used by n8n workflow trigger.

        Returns:
            Dictionary with scan results and file information
        """
        try:
            # Discover new files
            new_files = self.file_monitor.discover_new_files()

            # Process each new file for part mapping
            processed_files = []
            for file_obj in new_files:
                file_data = self._process_new_file(file_obj)
                processed_files.append(file_data)

            return {
                "success": True,
                "timestamp": datetime.now().isoformat(),
                "scan_directory": str(self.file_monitor.input_dir),
                "new_files_count": len(new_files),
                "new_files": processed_files,
                "total_monitored": len(self.file_monitor._tracked_files)
            }

        except Exception as e:
            logger.error(f"File scanning workflow error: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
                "new_files_count": 0,
                "new_files": []
            }

    def get_files_needing_processing(self) -> Dict[str, Any]:
        """
        Get files that need processing, including recovery.
        Used by n8n workflow for processing queue management.

        Returns:
            Dictionary with processable files
        """
        try:
            # Recover any incomplete files first
            recovered = self.file_monitor.scan_and_recover_incomplete()

            # Get all files needing processing
            processable_files = self.file_monitor.get_files_needing_processing()

            # Process file data for workflow
            processed_data = []
            for file_obj in processable_files:
                file_data = self._prepare_file_for_processing(file_obj)
                processed_data.append(file_data)

            return {
                "success": True,
                "timestamp": datetime.now().isoformat(),
                "recovered_files": len(recovered),
                "new_files_count": len(processable_files),
                "new_files": processed_data,
                "total_monitored": len(self.file_monitor._tracked_files)
            }

        except Exception as e:
            logger.error(f"Processable files workflow error: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
                "new_files_count": 0,
                "new_files": []
            }

    def _process_new_file(self, file_obj) -> Dict[str, Any]:
        """
        Process a newly discovered file with part mapping.

        Args:
            file_obj: ProcessedFile object

        Returns:
            File data dictionary for n8n workflow
        """
        # Attempt part number mapping
        mapping_result = None
        if not file_obj.part_number:
            mapping_result = self.part_mapper.map_filename_to_part_number(
                file_obj.metadata.filename
            )

            # If we found a mapping with good confidence, apply it
            if mapping_result.mapped_part_number and mapping_result.confidence_score > 0.7:
                self.file_monitor.add_file_part_number(
                    file_obj.metadata.file_id,
                    mapping_result.mapped_part_number,
                    mapping_result.confidence_score
                )

        # Determine processing type
        processing_type = "format_generation" if file_obj.metadata.is_psd else "background_removal"

        # Build file data for workflow
        file_data = {
            "file_id": file_obj.metadata.file_id,
            "filename": file_obj.metadata.filename,
            "file_type": file_obj.metadata.file_type,
            "size_mb": file_obj.metadata.size_mb,
            "is_psd": file_obj.metadata.is_psd,
            "path": str(file_obj.current_location),
            "status": file_obj.metadata.status,
            "checksum": file_obj.metadata.checksum_sha256,
            "processing_type": processing_type,
            "part_mapping": mapping_result.dict() if mapping_result else None,
            "requires_review": mapping_result.requires_manual_review if mapping_result else True
        }

        # Add part information if available
        if file_obj.part_number or (mapping_result and mapping_result.mapped_part_number):
            part_number = file_obj.part_number or mapping_result.mapped_part_number
            file_data["part_number"] = part_number

            # Get part metadata for enrichment
            from ..services.filemaker_service import FileMakerService
            filemaker = FileMakerService()
            part_metadata = filemaker.get_part_metadata(part_number)

            if part_metadata:
                file_data["part_metadata"] = {
                    "title": part_metadata.title,
                    "description": part_metadata.description,
                    "brand": part_metadata.part_brand,
                    "keywords": part_metadata.keywords
                }

        # Send discovery notification
        try:
            self.notifier.notify_file_discovered(file_obj)
        except Exception as e:
            logger.warning(f"Failed to send discovery notification: {e}")

        return file_data

    def _prepare_file_for_processing(self, file_obj) -> Dict[str, Any]:
        """
        Prepare file data for processing workflow.

        Args:
            file_obj: ProcessedFile object

        Returns:
            File data dictionary optimized for processing
        """
        # Check part mapping status
        needs_part_mapping = not file_obj.part_number
        mapping_confidence = 0.0

        if needs_part_mapping:
            # Attempt mapping if not already done
            mapping_result = self.part_mapper.map_filename_to_part_number(
                file_obj.metadata.filename
            )
            mapping_confidence = mapping_result.confidence_score

            # Apply mapping if confident
            if mapping_result.mapped_part_number and mapping_confidence > 0.7:
                self.file_monitor.add_file_part_number(
                    file_obj.metadata.file_id,
                    mapping_result.mapped_part_number,
                    mapping_confidence
                )
                needs_part_mapping = False

        # Determine processing path
        if file_obj.metadata.is_psd:
            processing_type = "format_generation"
            requires_bg_removal = False
        else:
            processing_type = "background_removal"
            requires_bg_removal = True

        return {
            "file_id": file_obj.metadata.file_id,
            "filename": file_obj.metadata.filename,
            "file_type": file_obj.metadata.file_type,
            "size_mb": file_obj.metadata.size_mb,
            "is_psd": file_obj.metadata.is_psd,
            "path": str(file_obj.current_location),
            "status": file_obj.metadata.status,
            "checksum": file_obj.metadata.checksum_sha256,
            "processing_type": processing_type,
            "requires_bg_removal": requires_bg_removal,
            "part_number": file_obj.part_number,
            "needs_part_mapping": needs_part_mapping,
            "mapping_confidence": mapping_confidence,
            "requires_manual_review": needs_part_mapping or mapping_confidence < 0.8
        }

    def get_file_status(self, file_id: str) -> Dict[str, Any]:
        """
        Get detailed status for a specific file.

        Args:
            file_id: File identifier

        Returns:
            File status information
        """
        try:
            file_obj = self.file_monitor.get_file_by_id(file_id)
            if not file_obj:
                return {
                    "success": False,
                    "error": f"File not found: {file_id}"
                }

            return {
                "success": True,
                "file_id": file_id,
                "status": file_obj.metadata.status,
                "filename": file_obj.metadata.filename,
                "part_number": file_obj.part_number,
                "processing_history": file_obj.processing_history,
                "current_location": str(file_obj.current_location) if file_obj.current_location else None
            }

        except Exception as e:
            logger.error(f"File status query error: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def update_file_status(self, file_id: str, new_status: str, reason: str = None) -> Dict[str, Any]:
        """
        Update file status (for n8n workflow integration).

        Args:
            file_id: File identifier
            new_status: New status to set
            reason: Optional reason for status change

        Returns:
            Update result
        """
        try:
            # Convert string status to enum
            status_enum = FileStatus(new_status)

            success = self.file_monitor.update_file_status(
                file_id, status_enum, reason
            )

            return {
                "success": success,
                "file_id": file_id,
                "new_status": new_status,
                "reason": reason,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"File status update error: {e}")
            return {
                "success": False,
                "file_id": file_id,
                "error": str(e)
            }


def main():
    """CLI entry point for n8n workflow calls."""
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Command required"}))
        sys.exit(1)

    command = sys.argv[1]
    workflow = FileMonitoringWorkflow()

    if command == "scan":
        result = workflow.scan_for_new_files()
    elif command == "processable":
        result = workflow.get_files_needing_processing()
    elif command == "status" and len(sys.argv) > 2:
        file_id = sys.argv[2]
        result = workflow.get_file_status(file_id)
    elif command == "update_status" and len(sys.argv) > 3:
        file_id = sys.argv[2]
        new_status = sys.argv[3]
        reason = sys.argv[4] if len(sys.argv) > 4 else None
        result = workflow.update_file_status(file_id, new_status, reason)
    else:
        result = {"error": f"Unknown command: {command}"}

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()