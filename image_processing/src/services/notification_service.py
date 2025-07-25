# ===== src/services/notification_service.py =====
"""
Teams Notification Service - Clean Architecture Implementation
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path

import requests
from jinja2 import Environment, DictLoader

from ..config.settings import settings
from ..utils.error_handling import handle_processing_errors

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Service for sending Teams notifications.

    Handles:
    - Teams webhook integration
    - Message template rendering
    - Notification status tracking
    """

    def __init__(self):
        self.webhook_url = settings.notifications.teams_webhook_url
        self.webhook_configured = bool(self.webhook_url)
        self.base_url = f"http://{settings.web.host}:{settings.web.port}"

        # Initialize message templates
        self.templates = Environment(loader=DictLoader(self._get_message_templates()))

        if not self.webhook_configured:
            logger.warning("Teams webhook URL not configured - notifications will be skipped")

    def _get_message_templates(self) -> Dict[str, str]:
        """Get Teams message templates."""
        return {
            'file_discovered': '''
{
    "@type": "MessageCard",
    "@context": "http://schema.org/extensions",
    "themeColor": "0078D4",
    "summary": "New File Discovered: {{ filename }}",
    "sections": [{
        "activityTitle": "📁 New File Discovered",
        "activitySubtitle": "{{ filename }}",
        "facts": [
            {
                "name": "File Size:",
                "value": "{{ file_size_mb }} MB"
            },
            {
                "name": "File Type:",
                "value": "{{ file_type }}"
            },
            {
                "name": "Processing Type:",
                "value": "{{ processing_type }}"
            }
        ],
        "markdown": true
    }],
    "potentialAction": [
        {
            "name": "View Dashboard",
            "type": "OpenUri",
            "uri": "{{ base_url }}"
        }
    ]
}
            ''',

            'processing_complete': '''
{
    "@type": "MessageCard",
    "@context": "http://schema.org/extensions",
    "themeColor": "28A745",
    "summary": "Processing Complete: {{ filename }}",
    "sections": [{
        "activityTitle": "✅ Processing Complete",
        "activitySubtitle": "{{ filename }}",
        "facts": [
            {
                "name": "Processing Type:",
                "value": "{{ processing_type }}"
            },
            {
                "name": "Processing Time:",
                "value": "{{ processing_time }}s"
            },
            {
                "name": "Quality Score:",
                "value": "{{ quality_score }}%"
            }
        ],
        "markdown": true
    }],
    "potentialAction": [
        {
            "name": "Review Result",
            "type": "OpenUri",
            "uri": "{{ base_url }}/review/{{ file_id }}"
        }
    ]
}
            ''',

            'formats_generated': '''
{
    "@type": "MessageCard",
    "@context": "http://schema.org/extensions",
    "themeColor": "28A745",
    "summary": "Production Formats Generated: {{ filename }}",
    "sections": [{
        "activityTitle": "🎉 Production Files Ready",
        "activitySubtitle": "{{ filename }}",
        "facts": [
            {
                "name": "Formats Generated:",
                "value": "{{ formats_count }} different formats"
            },
            {
                "name": "Processing Time:",
                "value": "{{ processing_time }}s"
            },
            {
                "name": "Ready for:",
                "value": "Web, Print, Social Media, E-commerce"
            }
        ],
        "markdown": true
    }],
    "potentialAction": [
        {
            "name": "Download Files",
            "type": "OpenUri",
            "uri": "{{ base_url }}/browse/production/"
        }
    ]
}
            ''',

            'processing_failed': '''
{
    "@type": "MessageCard",
    "@context": "http://schema.org/extensions",
    "themeColor": "DC3545",
    "summary": "Processing Failed: {{ filename }}",
    "sections": [{
        "activityTitle": "❌ Processing Failed",
        "activitySubtitle": "{{ filename }}",
        "facts": [
            {
                "name": "Error:",
                "value": "{{ error_message }}"
            },
            {
                "name": "Processing Type:",
                "value": "{{ processing_type }}"
            },
            {
                "name": "Status:",
                "value": "Requires manual intervention"
            }
        ],
        "markdown": true
    }],
    "potentialAction": [
        {
            "name": "View Dashboard",
            "type": "OpenUri",
            "uri": "{{ base_url }}"
        }
    ]
}
            '''
        }

    @handle_processing_errors("teams_notification")
    def send_notification(self, template_name: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send a notification to Teams.

        Args:
            template_name: Name of the message template to use
            context: Context data for template rendering

        Returns:
            Dictionary with sending result
        """
        if not self.webhook_configured:
            logger.debug(f"Skipping Teams notification '{template_name}' - webhook not configured")
            return {"status": "skipped", "reason": "Webhook not configured"}

        try:
            # Add base context
            context.update({
                "base_url": self.base_url,
                "timestamp": datetime.now().isoformat()
            })

            # Render message template
            if template_name not in self.templates.list_templates():
                raise ValueError(f"Unknown template: {template_name}")

            template = self.templates.get_template(template_name)
            message_json = template.render(context)

            # Parse JSON to validate
            message_data = json.loads(message_json)

            # Send to Teams
            response = requests.post(
                self.webhook_url,
                json=message_data,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )

            response.raise_for_status()

            logger.info(f"Teams notification sent successfully: {template_name}")

            return {
                "status": "success",
                "template": template_name,
                "status_code": response.status_code
            }

        except Exception as e:
            logger.error(f"Error sending Teams notification: {e}")
            return {
                "status": "error",
                "error": str(e),
                "template": template_name
            }

    def notify_file_discovered(self, file_obj) -> Dict[str, Any]:
        """Notify that a new file has been discovered."""
        context = {
            "filename": file_obj.metadata.filename,
            "file_id": file_obj.metadata.file_id,
            "file_size_mb": file_obj.metadata.size_mb,
            "file_type": file_obj.metadata.file_type,
            "processing_type": "PSD Direct Processing" if file_obj.metadata.is_psd else "Background Removal"
        }

        return self.send_notification('file_discovered', context)

    def notify_processing_complete(self, file_obj, result) -> Dict[str, Any]:
        """Notify that processing has completed."""
        context = {
            "filename": file_obj.metadata.filename,
            "file_id": file_obj.metadata.file_id,
            "processing_type": result.processing_type,
            "processing_time": round(result.processing_time_seconds, 1),
            "quality_score": result.quality_score or 0
        }

        return self.send_notification('processing_complete', context)

    def notify_formats_generated(self, file_obj, result) -> Dict[str, Any]:
        """Notify that production formats have been generated."""
        context = {
            "filename": file_obj.metadata.filename,
            "file_id": file_obj.metadata.file_id,
            "formats_count": result.metadata.get('successful_formats', 0),
            "processing_time": round(result.processing_time_seconds, 1)
        }

        return self.send_notification('formats_generated', context)

    def notify_processing_failed(self, file_obj, error_message: str, processing_type: str = "Unknown") -> Dict[
        str, Any]:
        """Notify that processing has failed."""
        context = {
            "filename": file_obj.metadata.filename,
            "file_id": file_obj.metadata.file_id,
            "error_message": error_message,
            "processing_type": processing_type
        }

        return self.send_notification('processing_failed', context)