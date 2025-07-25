#!/usr/bin/env python3
"""
Teams Notifier Server for Crown Automotive
Provides REST API for sending Teams notifications
"""

import os
import sys
import logging
from datetime import datetime
from typing import Dict, Any, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import structlog

# Import the teams notifier
sys.path.append('/scripts')
from teams_notifier import TeamsNotifier

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = structlog.get_logger(__name__)

# FastAPI app
app = FastAPI(
    title="Crown Automotive Teams Notifier",
    description="Teams notification service for image processing workflow",
    version="1.0.0"
)

# Global notifier instance
teams_notifier = None


class NotificationRequest(BaseModel):
    """Request model for notifications"""
    template_name: str
    context: Dict[str, Any]


class NotificationResponse(BaseModel):
    """Response model for notifications"""
    success: bool
    message: str
    template: str
    timestamp: str


@app.on_event("startup")
async def startup_event():
    """Initialize Teams notifier on startup"""
    global teams_notifier

    try:
        webhook_url = os.getenv('TEAMS_WEBHOOK_URL')
        teams_notifier = TeamsNotifier(webhook_url)

        if webhook_url:
            logger.info("Teams notifier initialized with webhook URL")
        else:
            logger.warning("Teams notifier initialized without webhook URL")

    except Exception as e:
        logger.error(f"Failed to initialize Teams notifier: {e}")
        raise


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "webhook_configured": bool(teams_notifier and teams_notifier.webhook_url)
    }


@app.post("/notify", response_model=NotificationResponse)
async def send_notification(request: NotificationRequest):
    """Send a Teams notification"""
    try:
        if not teams_notifier:
            raise Exception("Teams notifier not initialized")

        result = teams_notifier.send_notification(request.template_name, request.context)

        return NotificationResponse(
            success=result["status"] == "success",
            message=result.get("error", "Notification sent successfully"),
            template=request.template_name,
            timestamp=datetime.now().isoformat()
        )

    except Exception as e:
        logger.error(f"Notification error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/notify/psd_started")
async def notify_psd_processing_started(file_info: Dict[str, Any]):
    """Notify that PSD processing has started"""
    try:
        if not teams_notifier:
            raise Exception("Teams notifier not initialized")

        result = teams_notifier.notify_psd_processing_started(file_info)

        return NotificationResponse(
            success=result["status"] == "success",
            message=result.get("error", "PSD processing notification sent"),
            template="psd_processing_started",
            timestamp=datetime.now().isoformat()
        )

    except Exception as e:
        logger.error(f"PSD start notification error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/notify/psd_complete")
async def notify_psd_processing_complete(result: Dict[str, Any]):
    """Notify that PSD processing is complete"""
    try:
        if not teams_notifier:
            raise Exception("Teams notifier not initialized")

        result = teams_notifier.notify_psd_processing_complete(result)

        return NotificationResponse(
            success=result["status"] == "success",
            message=result.get("error", "PSD completion notification sent"),
            template="psd_processing_complete",
            timestamp=datetime.now().isoformat()
        )

    except Exception as e:
        logger.error(f"PSD complete notification error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/notify/bg_removal_complete")
async def notify_background_removal_complete(result: Dict[str, Any]):
    """Notify that background removal is complete"""
    try:
        if not teams_notifier:
            raise Exception("Teams notifier not initialized")

        result = teams_notifier.notify_background_removal_complete(result)

        return NotificationResponse(
            success=result["status"] == "success",
            message=result.get("error", "Background removal notification sent"),
            template="background_removal_complete",
            timestamp=datetime.now().isoformat()
        )

    except Exception as e:
        logger.error(f"Background removal notification error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/notify/processing_approved")
async def notify_processing_approved(result: Dict[str, Any]):
    """Notify that image processing was approved"""
    try:
        if not teams_notifier:
            raise Exception("Teams notifier not initialized")

        result = teams_notifier.notify_processing_approved(result)

        return NotificationResponse(
            success=result["status"] == "success",
            message=result.get("error", "Processing approved notification sent"),
            template="processing_approved",
            timestamp=datetime.now().isoformat()
        )

    except Exception as e:
        logger.error(f"Processing approved notification error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/notify/processing_rejected")
async def notify_processing_rejected(file_info: Dict[str, Any], reason: Optional[str] = None):
    """Notify that image processing was rejected"""
    try:
        if not teams_notifier:
            raise Exception("Teams notifier not initialized")

        result = teams_notifier.notify_processing_rejected(file_info, reason)

        return NotificationResponse(
            success=result["status"] == "success",
            message=result.get("error", "Processing rejected notification sent"),
            template="processing_rejected",
            timestamp=datetime.now().isoformat()
        )

    except Exception as e:
        logger.error(f"Processing rejected notification error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/notify/daily_summary")
async def send_daily_summary(stats: Dict[str, Any]):
    """Send daily processing summary"""
    try:
        if not teams_notifier:
            raise Exception("Teams notifier not initialized")

        result = teams_notifier.send_daily_summary(stats)

        return NotificationResponse(
            success=result["status"] == "success",
            message=result.get("error", "Daily summary sent"),
            template="daily_summary",
            timestamp=datetime.now().isoformat()
        )

    except Exception as e:
        logger.error(f"Daily summary notification error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/templates")
async def list_templates():
    """List available notification templates"""
    try:
        if not teams_notifier:
            raise Exception("Teams notifier not initialized")

        templates = teams_notifier.templates.list_templates()

        return {
            "templates": templates,
            "total": len(templates)
        }

    except Exception as e:
        logger.error(f"List templates error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/status")
async def get_status():
    """Get detailed notifier status"""
    try:
        return {
            "status": "running",
            "webhook_configured": bool(teams_notifier and teams_notifier.webhook_url),
            "webhook_url_set": bool(os.getenv('TEAMS_WEBHOOK_URL')),
            "base_url": teams_notifier.base_url if teams_notifier else None,
            "last_check": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Status error: {e}")
        return {"status": "error", "error": str(e)}


@app.post("/test")
async def test_notification():
    """Send a test notification"""
    try:
        if not teams_notifier:
            raise Exception("Teams notifier not initialized")

        test_data = {
            "filename": "test-image.jpg",
            "file_size_mb": 2.5,
            "dimensions": {"width": 2000, "height": 2000}
        }

        result = teams_notifier.notify_psd_processing_started(test_data)

        return {
            "test_sent": result["status"] == "success",
            "result": result,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Test notification error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    # Run the server
    uvicorn.run(
        "notifier_server:app",
        host="0.0.0.0",
        port=8004,
        log_level="info",
        access_log=True
    )