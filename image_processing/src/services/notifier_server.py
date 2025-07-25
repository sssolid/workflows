# ===== src/services/notifier_server.py =====
"""
Teams Notifier Server - Clean Architecture Implementation
Provides REST API for sending Teams notifications
"""

import logging
from datetime import datetime
from typing import Dict, Any

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from ..config.settings import settings
from ..services.notification_service import NotificationService
from ..utils.logging_config import setup_logging

# Setup logging
setup_logging(settings.log_level)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="Crown Automotive Teams Notifier",
    description="Teams notification service for image processing workflow",
    version="1.0.0"
)

# Global notifier instance
notifier: NotificationService = None


class NotificationRequest(BaseModel):
    """Request model for notifications."""
    template_name: str
    context: Dict[str, Any]


@app.on_event("startup")
async def startup_event():
    """Initialize notifier on startup."""
    global notifier

    try:
        logger.info("Initializing Teams notifier...")
        notifier = NotificationService()
        logger.info("Teams notifier initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Teams notifier: {e}")
        raise


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "webhook_configured": bool(notifier and notifier.webhook_configured) if notifier else False
    }


@app.post("/notify")
async def send_notification(request: NotificationRequest) -> Dict[str, Any]:
    """Send a Teams notification."""
    try:
        if not notifier:
            raise HTTPException(status_code=503, detail="Notifier not initialized")

        result = notifier.send_notification(request.template_name, request.context)

        return {
            "success": result.get("status") == "success",
            "message": result.get("error", "Notification sent successfully"),
            "template": request.template_name,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Notification error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/status")
async def get_status():
    """Get detailed notifier status."""
    try:
        return {
            "status": "running",
            "webhook_configured": bool(notifier and notifier.webhook_configured) if notifier else False,
            "last_check": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Status error: {e}")
        return {"status": "error", "error": str(e)}


def main():
    """Main entry point."""
    logger.info("Starting Crown Automotive Teams Notifier...")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8004,
        log_level="info",
        access_log=True
    )


if __name__ == "__main__":
    main()
