# ===== src/services/ml_server.py =====
"""
ML Processing Server - Clean Architecture Implementation
Provides REST API for background removal and other ML operations
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..config.settings import settings
from ..services.background_removal_service import BackgroundRemovalService
from ..services.file_monitor_service import FileMonitorService
from ..models.processing_models import BackgroundRemovalRequest, ProcessingResult
from ..utils.logging_config import setup_logging

# Setup logging
setup_logging(settings.log_level)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="Crown Automotive ML Processor",
    description="Background removal and ML processing for automotive parts",
    version="1.0.0"
)

# Global services
bg_removal_service: Optional[BackgroundRemovalService] = None
file_monitor: Optional[FileMonitorService] = None


class ProcessingRequestAPI(BaseModel):
    """API request model for processing operations."""
    file_id: str
    model: str = "isnet-general-use"
    enhance_input: bool = True
    post_process: bool = True
    alpha_threshold: int = 40


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    global bg_removal_service, file_monitor

    try:
        logger.info("Initializing ML services...")
        bg_removal_service = BackgroundRemovalService()
        file_monitor = FileMonitorService()
        logger.info("ML services initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize ML services: {e}")
        raise


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "background_removal": bg_removal_service is not None,
            "file_monitor": file_monitor is not None
        }
    }


@app.post("/remove_background")
async def remove_background_api(request: ProcessingRequestAPI) -> Dict[str, Any]:
    """Remove background from image via API."""
    try:
        if not bg_removal_service or not file_monitor:
            raise HTTPException(status_code=503, detail="Services not initialized")

        # Get file object
        file_obj = file_monitor.get_file_by_id(request.file_id)
        if not file_obj:
            raise HTTPException(status_code=404, detail=f"File not found: {request.file_id}")

        # Create processing request
        bg_request = BackgroundRemovalRequest(
            file_id=request.file_id,
            model=request.model,
            enhance_input=request.enhance_input,
            post_process=request.post_process,
            alpha_threshold=request.alpha_threshold
        )

        # Process the image
        result = bg_removal_service.remove_background(file_obj, bg_request)

        # Update file status
        if result.success:
            file_monitor.update_file_status(
                request.file_id,
                "awaiting_review",
                "Background removal completed",
                result.output_path
            )
        else:
            file_monitor.update_file_status(
                request.file_id,
                "failed",
                result.error_message
            )

        return {
            "success": result.success,
            "message": "Background removal completed" if result.success else result.error_message,
            "file_id": request.file_id,
            "processing_time": result.processing_time_seconds,
            "quality_score": result.quality_score,
            "output_path": str(result.output_path) if result.output_path else None,
            "model_used": result.model_used
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Background removal API error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/models")
async def list_models():
    """List available background removal models."""
    return {
        "available_models": [
            {"value": "isnet-general-use", "name": "ISNet General Use", "recommended": True},
            {"value": "u2net", "name": "U2Net", "recommended": False},
            {"value": "u2net_human_seg", "name": "U2Net Human Segmentation", "recommended": False},
            {"value": "silueta", "name": "Silueta", "recommended": False}
        ]
    }


@app.get("/status")
async def get_status():
    """Get detailed status information."""
    try:
        return {
            "service": "Crown Automotive ML Processor",
            "status": "running",
            "timestamp": datetime.now().isoformat(),
            "services": {
                "background_removal": bg_removal_service is not None,
                "file_monitor": file_monitor is not None
            },
            "models_loaded": len(bg_removal_service.models_cache) if bg_removal_service else 0
        }
    except Exception as e:
        logger.error(f"Status check error: {e}")
        return {
            "service": "Crown Automotive ML Processor",
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


def main():
    """Main entry point."""
    logger.info("Starting Crown Automotive ML Processor...")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8001,
        log_level="info",
        access_log=True
    )


if __name__ == "__main__":
    main()