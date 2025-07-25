# ===== src/workflows/processing_orchestrator.py =====
"""
Processing Orchestration for n8n workflows.
Handles the coordination of different processing steps.
"""

import json
import sys
import logging
from datetime import datetime
from typing import Dict, Any, List

from ..services.file_monitor_service import FileMonitorService
from ..services.background_removal_service import BackgroundRemovalService
from ..services.image_processing_service import ImageProcessingService
from ..services.notification_service import NotificationService
from ..models.processing_models import BackgroundRemovalRequest, FormatGenerationRequest, ProcessingModel
from ..models.file_models import FileStatus
from ..utils.logging_config import setup_logging

logger = logging.getLogger(__name__)


class ProcessingOrchestrator:
    """Orchestration class for n8n processing workflows."""

    def __init__(self):
        self.file_monitor = FileMonitorService()
        self.bg_removal = BackgroundRemovalService()
        self.image_processor = ImageProcessingService()
        self.notifier = NotificationService()

    def process_file(self, file_id: str, processing_type: str, **kwargs) -> Dict[str, Any]:
        """
        Process a file based on the processing type.

        Args:
            file_id: File identifier
            processing_type: Type of processing to perform
            **kwargs: Additional processing parameters

        Returns:
            Processing result dictionary
        """
        try:
            # Get file object
            file_obj = self.file_monitor.get_file_by_id(file_id)
            if not file_obj:
                return {
                    "success": False,
                    "error": f"File not found: {file_id}",
                    "timestamp": datetime.now().isoformat()
                }

            # Update status to processing
            self.file_monitor.update_file_status(file_id, FileStatus.PROCESSING)

            if processing_type == "background_removal":
                result = self._process_background_removal(file_obj, **kwargs)
            elif processing_type == "format_generation":
                result = self._process_format_generation(file_obj, **kwargs)
            else:
                return {
                    "success": False,
                    "error": f"Unknown processing type: {processing_type}",
                    "timestamp": datetime.now().isoformat()
                }

            # Update file status based on result
            if result.success:
                if processing_type == "background_removal":
                    self.file_monitor.update_file_status(
                        file_id,
                        FileStatus.AWAITING_REVIEW,
                        "Background removal completed",
                        result.output_path
                    )
                    # Send notification
                    self.notifier.notify_processing_complete(file_obj, result)
                else:
                    self.file_monitor.update_file_status(
                        file_id,
                        FileStatus.APPROVED,
                        "Format generation completed"
                    )
                    # Send notification
                    self.notifier.notify_formats_generated(file_obj, result)
            else:
                self.file_monitor.update_file_status(
                    file_id,
                    FileStatus.FAILED,
                    result.error_message
                )
                # Send failure notification
                self.notifier.notify_processing_failed(file_obj, result.error_message, processing_type)

            return {
                "success": result.success,
                "file_id": file_id,
                "processing_type": processing_type,
                "processing_time": result.processing_time_seconds,
                "error": result.error_message if not result.success else None,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Processing orchestration error: {e}")
            # Update status to failed
            self.file_monitor.update_file_status(file_id, FileStatus.FAILED, str(e))

            return {
                "success": False,
                "file_id": file_id,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    def _process_background_removal(self, file_obj, **kwargs) -> Any:
        """Process background removal for a file."""
        request = BackgroundRemovalRequest(
            file_id=file_obj.metadata.file_id,
            model=ProcessingModel(kwargs.get('model', 'isnet-general-use')),
            enhance_input=kwargs.get('enhance_input', True),
            post_process=kwargs.get('post_process', True),
            alpha_threshold=kwargs.get('alpha_threshold', 40)
        )

        return self.bg_removal.remove_background(file_obj, request)

    def _process_format_generation(self, file_obj, **kwargs) -> Any:
        """Process format generation for a file."""
        # Get all available formats
        output_formats = kwargs.get('output_formats')
        if not output_formats:
            output_formats = [spec['name'] for spec in self.image_processor.output_specs]

        request = FormatGenerationRequest(
            file_id=file_obj.metadata.file_id,
            output_formats=output_formats,
            include_watermark=kwargs.get('include_watermark', False),
            include_brand_icon=kwargs.get('include_brand_icon', True)
        )

        return self.image_processor.generate_formats(file_obj, request)

    def handle_approval(self, file_id: str) -> Dict[str, Any]:
        """
        Handle file approval and trigger format generation.

        Args:
            file_id: File identifier

        Returns:
            Processing result dictionary
        """
        return self.process_file(file_id, "format_generation")

    def handle_rejection(self, file_id: str, reason: str = "Manual review required") -> Dict[str, Any]:
        """
        Handle file rejection.

        Args:
            file_id: File identifier
            reason: Rejection reason

        Returns:
            Result dictionary
        """
        try:
            success = self.file_monitor.update_file_status(
                file_id,
                FileStatus.REJECTED,
                reason
            )

            if success:
                file_obj = self.file_monitor.get_file_by_id(file_id)
                if file_obj:
                    self.notifier.notify_processing_failed(file_obj, reason, "manual_review")

            return {
                "success": success,
                "file_id": file_id,
                "action": "rejected",
                "reason": reason,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Rejection handling error: {e}")
            return {
                "success": False,
                "file_id": file_id,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }


def main():
    """CLI entry point for n8n to call."""
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Command required"}))
        sys.exit(1)

    command = sys.argv[1]
    orchestrator = ProcessingOrchestrator()

    if command == "process":
        if len(sys.argv) < 4:
            print(json.dumps({"error": "File ID and processing type required"}))
            sys.exit(1)

        file_id = sys.argv[2]
        processing_type = sys.argv[3]

        # Parse additional arguments from JSON if provided
        kwargs = {}
        if len(sys.argv) > 4:
            try:
                kwargs = json.loads(sys.argv[4])
            except json.JSONDecodeError:
                logger.warning("Invalid JSON parameters provided")

        result = orchestrator.process_file(file_id, processing_type, **kwargs)

    elif command == "approve":
        if len(sys.argv) < 3:
            print(json.dumps({"error": "File ID required"}))
            sys.exit(1)

        file_id = sys.argv[2]
        result = orchestrator.handle_approval(file_id)

    elif command == "reject":
        if len(sys.argv) < 3:
            print(json.dumps({"error": "File ID required"}))
            sys.exit(1)

        file_id = sys.argv[2]
        reason = sys.argv[3] if len(sys.argv) > 3 else "Manual review required"
        result = orchestrator.handle_rejection(file_id, reason)

    else:
        result = {"error": f"Unknown command: {command}"}

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()