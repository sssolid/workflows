#!/usr/bin/env python3
"""
Microsoft Teams Notifier for Crown Automotive Image Processing
Sends formatted notifications to Teams channels about processing status
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
import asyncio

import requests
import httpx
from jinja2 import Environment, DictLoader

logger = logging.getLogger(__name__)

# Configuration
TEAMS_WEBHOOK_URL = os.getenv('TEAMS_WEBHOOK_URL')
SERVER_HOST = os.getenv('IMAGE_SERVER_HOST', 'localhost')
SERVER_PORT = os.getenv('IMAGE_SERVER_PORT', '8080')
BASE_URL = f"http://{SERVER_HOST}:{SERVER_PORT}"


class TeamsNotifier:
    """Microsoft Teams notification handler"""

    def __init__(self, webhook_url: Optional[str] = None):
        """
        Initialize Teams notifier

        Args:
            webhook_url: Teams webhook URL, defaults to environment variable
        """
        self.webhook_url = webhook_url or TEAMS_WEBHOOK_URL
        if not self.webhook_url:
            logger.warning("No Teams webhook URL configured")

        self.base_url = BASE_URL

        # Message templates
        self.templates = Environment(loader=DictLoader(self._get_message_templates()))

    def _get_message_templates(self) -> Dict[str, str]:
        """Get Teams message templates"""
        return {
            'psd_processing_started': '''
{
    "@type": "MessageCard",
    "@context": "http://schema.org/extensions",
    "themeColor": "0078D4",
    "summary": "PSD Processing Started: {{ filename }}",
    "sections": [{
        "activityTitle": "🔄 PSD Processing Started",
        "activitySubtitle": "{{ filename }}",
        "facts": [
            {
                "name": "File Size:",
                "value": "{{ file_size_mb }} MB"
            },
            {
                "name": "Dimensions:",
                "value": "{{ dimensions.width }}x{{ dimensions.height }}"
            },
            {
                "name": "Estimated Time:",
                "value": "2-3 minutes"
            }
        ],
        "markdown": true
    }]
}
            ''',

            'psd_processing_complete': '''
{
    "@type": "MessageCard",
    "@context": "http://schema.org/extensions",
    "themeColor": "28A745",
    "summary": "PSD Processing Complete: {{ filename }}",
    "sections": [{
        "activityTitle": "✅ PSD Processing Complete",
        "activitySubtitle": "{{ filename }}",
        "activityImage": "{{ preview_url }}",
        "facts": [
            {
                "name": "Part Number:",
                "value": "{{ part_metadata.PartNumber | default('Unknown') }}"
            },
            {
                "name": "Description:",
                "value": "{{ part_metadata.Title | default('No description') }}"
            },
            {
                "name": "Brand:",
                "value": "{{ part_metadata.PartBrand | default('Crown Automotive') }}"
            },
            {
                "name": "Formats Generated:",
                "value": "{{ formats_count }} different sizes/formats"
            },
            {
                "name": "Processing Time:",
                "value": "{{ processing_time }}s"
            }
        ],
        "markdown": true
    }],
    "potentialAction": [
        {
            "name": "View All Files",
            "type": "OpenUri",
            "uri": "{{ base_url }}/browse/production/"
        },
        {
            "name": "High-Res TIFF (2500px)",
            "type": "OpenUri",
            "uri": "{{ download_links.tiff_2500 }}"
        },
        {
            "name": "Web JPEG (1000px)",
            "type": "OpenUri",
            "uri": "{{ download_links.jpeg_1000 }}"
        },
        {
            "name": "Dashboard",
            "type": "OpenUri",
            "uri": "{{ base_url }}/"
        }
    ]
}
            ''',

            'background_removal_complete': '''
{
    "@type": "MessageCard",
    "@context": "http://schema.org/extensions",
    "themeColor": "17A2B8",
    "summary": "Background Removal Review: {{ filename }}",
    "sections": [{
        "activityTitle": "🖼️ Background Removal Complete - Review Required",
        "activitySubtitle": "{{ filename }}",
        "activityImage": "{{ preview_url }}",
        "facts": [
            {
                "name": "Part Number:",
                "value": "{{ part_metadata.PartNumber | default('Unknown') }}"
            },
            {
                "name": "Description:",
                "value": "{{ part_metadata.Title | default('No description') }}"
            },
            {
                "name": "Brand:",
                "value": "{{ part_metadata.PartBrand | default('Crown Automotive') }}"
            },
            {
                "name": "Original Size:",
                "value": "{{ original_size.width }}x{{ original_size.height }}"
            },
            {
                "name": "Processing Time:",
                "value": "{{ processing_time }}s"
            },
            {
                "name": "Model Used:",
                "value": "{{ model_used | default('isnet-general-use') }}"
            }
        ],
        "markdown": true,
        "text": "Please review the background removal result. If approved, the image will be processed into all production formats."
    }],
    "potentialAction": [
        {
            "name": "🔍 Review Images",
            "type": "OpenUri",
            "uri": "{{ review_url }}"
        },
        {
            "name": "📊 View EXIF Data",
            "type": "OpenUri",
            "uri": "{{ exif_url }}"
        },
        {
            "name": "📈 Dashboard",
            "type": "OpenUri",
            "uri": "{{ base_url }}/"
        }
    ]
}
            ''',

            'processing_approved': '''
{
    "@type": "MessageCard",
    "@context": "http://schema.org/extensions",
    "themeColor": "28A745",
    "summary": "Production Processing Complete: {{ filename }}",
    "sections": [{
        "activityTitle": "🎉 Image Approved - Production Files Ready",
        "activitySubtitle": "{{ filename }}",
        "activityImage": "{{ preview_url }}",
        "facts": [
            {
                "name": "Part Number:",
                "value": "{{ part_metadata.PartNumber | default('Unknown') }}"
            },
            {
                "name": "Description:",
                "value": "{{ part_metadata.Title | default('No description') }}"
            },
            {
                "name": "Brand:",
                "value": "{{ part_metadata.PartBrand | default('Crown Automotive') }}"
            },
            {
                "name": "Total Files Generated:",
                "value": "{{ formats_count }} formats ready for use"
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
            "name": "📁 Download All Files",
            "type": "OpenUri",
            "uri": "{{ base_url }}/browse/production/"
        },
        {
            "name": "🖼️ High-Res TIFF",
            "type": "OpenUri",
            "uri": "{{ download_links.tiff_2500 }}"
        },
        {
            "name": "🌐 Web JPEG",
            "type": "OpenUri",
            "uri": "{{ download_links.jpeg_1000 }}"
        },
        {
            "name": "📱 Thumbnails",
            "type": "OpenUri",
            "uri": "{{ download_links.thumbnails }}"
        }
    ]
}
            ''',

            'processing_rejected': '''
{
    "@type": "MessageCard",
    "@context": "http://schema.org/extensions",
    "themeColor": "DC3545",
    "summary": "Image Processing Rejected: {{ filename }}",
    "sections": [{
        "activityTitle": "❌ Image Rejected - Manual Review Required",
        "activitySubtitle": "{{ filename }}",
        "facts": [
            {
                "name": "Part Number:",
                "value": "{{ part_metadata.PartNumber | default('Unknown') }}"
            },
            {
                "name": "Description:",
                "value": "{{ part_metadata.Title | default('No description') }}"
            },
            {
                "name": "Reason:",
                "value": "{{ rejection_reason | default('Background removal quality insufficient') }}"
            },
            {
                "name": "Next Steps:",
                "value": "File moved to manual review queue"
            }
        ],
        "markdown": true
    }],
    "potentialAction": [
        {
            "name": "🔄 Retry Processing",
            "type": "OpenUri",
            "uri": "{{ retry_url }}"
        },
        {
            "name": "📂 Manual Review Queue",
            "type": "OpenUri",
            "uri": "{{ base_url }}/browse/rejected/"
        }
    ]
}
            ''',

            'processing_error': '''
{
    "@type": "MessageCard",
    "@context": "http://schema.org/extensions",
    "themeColor": "FF6900",
    "summary": "Processing Error: {{ filename }}",
    "sections": [{
        "activityTitle": "⚠️ Image Processing Error",
        "activitySubtitle": "{{ filename }}",
        "facts": [
            {
                "name": "Error Type:",
                "value": "{{ error_type | default('Processing Error') }}"
            },
            {
                "name": "Error Message:",
                "value": "{{ error_message }}"
            },
            {
                "name": "Time:",
                "value": "{{ timestamp }}"
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
            "name": "📋 View Logs",
            "type": "OpenUri",
            "uri": "{{ base_url }}/browse/logs/"
        },
        {
            "name": "🔧 System Dashboard",
            "type": "OpenUri",
            "uri": "{{ base_url }}/"
        }
    ]
}
            ''',

            'daily_summary': '''
{
    "@type": "MessageCard",
    "@context": "http://schema.org/extensions",
    "themeColor": "0078D4",
    "summary": "Daily Processing Summary - {{ date }}",
    "sections": [{
        "activityTitle": "📊 Daily Image Processing Summary",
        "activitySubtitle": "{{ date }}",
        "facts": [
            {
                "name": "Total Files Processed:",
                "value": "{{ stats.total_processed }}"
            },
            {
                "name": "PSD Files:",
                "value": "{{ stats.psd_files }}"
            },
            {
                "name": "Background Removals:",
                "value": "{{ stats.bg_removed }}"
            },
            {
                "name": "Approved:",
                "value": "{{ stats.approved }}"
            },
            {
                "name": "Rejected:",
                "value": "{{ stats.rejected }}"
            },
            {
                "name": "Errors:",
                "value": "{{ stats.errors }}"
            },
            {
                "name": "Total Production Files:",
                "value": "{{ stats.production_files }}"
            }
        ],
        "markdown": true
    }],
    "potentialAction": [
        {
            "name": "📈 View Dashboard",
            "type": "OpenUri",
            "uri": "{{ base_url }}/"
        },
        {
            "name": "📁 Browse Files",
            "type": "OpenUri",
            "uri": "{{ base_url }}/browse/production/"
        }
    ]
}
            '''
        }

    def send_notification(self, template_name: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send a notification to Teams

        Args:
            template_name: Name of the message template to use
            context: Context data for template rendering

        Returns:
            Dictionary with sending result
        """
        try:
            if not self.webhook_url:
                logger.warning("No Teams webhook URL configured, skipping notification")
                return {"status": "skipped", "reason": "No webhook URL"}

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

        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending Teams notification: {e}")
            return {
                "status": "error",
                "error": str(e),
                "template": template_name
            }
        except Exception as e:
            logger.error(f"Unexpected error sending Teams notification: {e}")
            return {
                "status": "error",
                "error": str(e),
                "template": template_name
            }

    def notify_psd_processing_started(self, file_info: Dict[str, Any]) -> Dict[str, Any]:
        """Notify that PSD processing has started"""
        context = {
            "filename": file_info.get("filename", "unknown.psd"),
            "file_size_mb": file_info.get("file_size_mb", 0),
            "dimensions": file_info.get("dimensions", {"width": 0, "height": 0})
        }

        return self.send_notification('psd_processing_started', context)

    def notify_psd_processing_complete(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Notify that PSD processing is complete"""
        filename = result.get("base_name", "unknown")

        context = {
            "filename": result.get("file", "unknown.psd"),
            "part_metadata": result.get("part_metadata", {}),
            "formats_count": result.get("successful_variants", 0),
            "processing_time": result.get("processing_time_seconds", 0),
            "preview_url": f"{self.base_url}/production/1000x1000_72dpi_jpeg/{filename}.jpg",
            "download_links": {
                "tiff_2500": f"{self.base_url}/production/2500x2500_300dpi_tiff/{filename}.tiff",
                "jpeg_1000": f"{self.base_url}/production/1000x1000_72dpi_jpeg/{filename}.jpg"
            }
        }

        return self.send_notification('psd_processing_complete', context)

    def notify_background_removal_complete(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Notify that background removal is complete and needs review"""
        filename = Path(result.get("input_file", "unknown")).name
        base_name = Path(filename).stem

        context = {
            "filename": filename,
            "part_metadata": result.get("part_metadata", {}),
            "original_size": result.get("original_size", {"width": 0, "height": 0}),
            "processing_time": result.get("processing_time_seconds", 0),
            "model_used": result.get("model_used", "isnet-general-use"),
            "preview_url": f"{self.base_url}/bg_removed/{base_name}_bg_removed.png",
            "review_url": f"{self.base_url}/review/{filename}",
            "exif_url": f"{self.base_url}/exif/{filename}"
        }

        return self.send_notification('background_removal_complete', context)

    def notify_processing_approved(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Notify that image was approved and production processing is complete"""
        filename = result.get("base_name", "unknown")

        context = {
            "filename": result.get("file", "unknown"),
            "part_metadata": result.get("part_metadata", {}),
            "formats_count": result.get("successful_variants", 0),
            "preview_url": f"{self.base_url}/production/1000x1000_72dpi_jpeg/{filename}.jpg",
            "download_links": {
                "tiff_2500": f"{self.base_url}/production/2500x2500_300dpi_tiff/{filename}.tiff",
                "jpeg_1000": f"{self.base_url}/production/1000x1000_72dpi_jpeg/{filename}.jpg",
                "thumbnails": f"{self.base_url}/browse/production/"
            }
        }

        return self.send_notification('processing_approved', context)

    def notify_processing_rejected(self, file_info: Dict[str, Any], reason: str = None) -> Dict[str, Any]:
        """Notify that image processing was rejected"""
        context = {
            "filename": file_info.get("filename", "unknown"),
            "part_metadata": file_info.get("part_metadata", {}),
            "rejection_reason": reason or "Background removal quality insufficient",
            "retry_url": f"{self.base_url}/review/{file_info.get('filename', 'unknown')}"
        }

        return self.send_notification('processing_rejected', context)

    def notify_processing_error(self, error_info: Dict[str, Any]) -> Dict[str, Any]:
        """Notify about processing errors"""
        context = {
            "filename": error_info.get("filename", "unknown"),
            "error_type": error_info.get("error_type", "Processing Error"),
            "error_message": error_info.get("error_message", "Unknown error"),
            "timestamp": error_info.get("timestamp", datetime.now().isoformat())
        }

        return self.send_notification('processing_error', context)

    def send_daily_summary(self, stats: Dict[str, Any]) -> Dict[str, Any]:
        """Send daily processing summary"""
        context = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "stats": stats
        }

        return self.send_notification('daily_summary', context)

    async def send_notification_async(self, template_name: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send notification asynchronously

        Args:
            template_name: Name of the message template to use
            context: Context data for template rendering

        Returns:
            Dictionary with sending result
        """
        try:
            if not self.webhook_url:
                logger.warning("No Teams webhook URL configured, skipping notification")
                return {"status": "skipped", "reason": "No webhook URL"}

            # Add base context
            context.update({
                "base_url": self.base_url,
                "timestamp": datetime.now().isoformat()
            })

            # Render message template
            template = self.templates.get_template(template_name)
            message_json = template.render(context)
            message_data = json.loads(message_json)

            # Send to Teams asynchronously
            async with httpx.AsyncClient() as client:
                response = await client.post(
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
            logger.error(f"Error sending async Teams notification: {e}")
            return {
                "status": "error",
                "error": str(e),
                "template": template_name
            }


def main():
    """Test Teams notifications"""
    import argparse

    parser = argparse.ArgumentParser(description='Test Teams notifications')
    parser.add_argument('--webhook-url', help='Teams webhook URL')
    parser.add_argument('--template', choices=[
        'psd_processing_started', 'psd_processing_complete', 'background_removal_complete',
        'processing_approved', 'processing_rejected', 'processing_error', 'daily_summary'
    ], help='Template to test')
    parser.add_argument('--test-data', help='JSON file with test data')

    args = parser.parse_args()

    notifier = TeamsNotifier(args.webhook_url)

    if args.template:
        # Create sample test data based on template
        test_data = {}

        if args.template == 'psd_processing_started':
            test_data = {
                "filename": "test-part-123.psd",
                "file_size_mb": 15.2,
                "dimensions": {"width": 3000, "height": 3000}
            }

        elif args.template == 'background_removal_complete':
            test_data = {
                "input_file": "/data/input/test-part-123.jpg",
                "part_metadata": {
                    "PartNumber": "TEST123",
                    "Title": "Test Automotive Part",
                    "PartBrand": "Crown Automotive"
                },
                "original_size": {"width": 2500, "height": 2500},
                "processing_time_seconds": 15.3,
                "model_used": "isnet-general-use"
            }

        elif args.template == 'daily_summary':
            test_data = {
                "stats": {
                    "total_processed": 25,
                    "psd_files": 10,
                    "bg_removed": 15,
                    "approved": 22,
                    "rejected": 2,
                    "errors": 1,
                    "production_files": 528
                }
            }

        # Load custom test data if provided
        if args.test_data and Path(args.test_data).exists():
            with open(args.test_data) as f:
                test_data.update(json.load(f))

        print(f"Sending test notification: {args.template}")
        result = notifier.send_notification(args.template, test_data)

        if result["status"] == "success":
            print("✅ Notification sent successfully!")
        else:
            print(f"❌ Failed to send notification: {result.get('error', 'Unknown error')}")

    else:
        print("Available templates:")
        for template in notifier.templates.list_templates():
            print(f"  - {template}")


if __name__ == "__main__":
    main()