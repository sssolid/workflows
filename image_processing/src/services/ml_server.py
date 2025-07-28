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
import httpx
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..config.settings import settings
from ..services.background_removal_service import BackgroundRemovalService
from ..models.processing_models import BackgroundRemovalRequest, ProcessingResult
from ..models.file_models import ProcessedFile, FileMetadata, FileType, FileStatus
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

# File monitor service URL
FILE_MONITOR_URL = "http://file_monitor:8002"


class ProcessingRequestAPI(BaseModel):
    """API request model for processing operations."""
    file_id: str
    model: str = "isnet-general-use"
    enhance_input: bool = True
    post_process: bool = True
    alpha_threshold: int = 40


async def get_file_from_monitor(file_id: str) -> Optional[ProcessedFile]:
    """Get file data from file monitor service via API."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{FILE_MONITOR_URL}/files/{file_id}")

            if response.status_code == 404:
                return None
            elif response.status_code != 200:
                logger.error(f"File monitor API error: {response.status_code}")
                return None

            file_data = response.json()

            # Convert API response back to ProcessedFile object
            metadata = FileMetadata(
                file_id=file_data["file_id"],
                original_path=Path(file_data["current_location"]),
                filename=file_data["filename"],
                file_type=FileType(file_data["file_type"]),
                size_bytes=int(file_data["size_mb"] * 1024 * 1024),  # Convert back to bytes
                checksum_md5="",  # Not needed for processing
                checksum_sha256=file_data["checksum"],
                modified_at=datetime.now(),
                status=FileStatus(file_data["status"])
            )

            processed_file = ProcessedFile(
                metadata=metadata,
                current_location=Path(file_data["current_location"]),
                part_number=file_data.get("part_number"),
                processing_history=file_data.get("processing_history", [])
            )

            return processed_file

    except Exception as e:
        logger.error(f"Error getting file from monitor: {e}")
        return None


async def update_file_status(file_id: str, status: str, reason: str = None, new_location: str = None) -> bool:
    """Update file status via file monitor API."""
    try:
        async with httpx.AsyncClient() as client:
            params = {"status": status}
            if reason:
                params["reason"] = reason

            response = await client.put(f"{FILE_MONITOR_URL}/files/{file_id}/status",
                                        params=params)

            # TODO: Add support for updating file location in the API
            # For now, we'll handle location updates separately if needed

            return response.status_code == 200

    except Exception as e:
        logger.error(f"Error updating file status: {e}")
        return False


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    global bg_removal_service

    try:
        logger.info("Initializing ML services...")
        bg_removal_service = BackgroundRemovalService()
        logger.info("ML services initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize ML services: {e}")
        raise


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    # Test connection to file monitor
    file_monitor_healthy = False
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{FILE_MONITOR_URL}/health", timeout=5.0)
            file_monitor_healthy = response.status_code == 200
    except:
        pass

    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "background_removal": bg_removal_service is not None,
            "file_monitor_api": file_monitor_healthy
        }
    }


@app.post("/remove_background")
async def remove_background_api(request: ProcessingRequestAPI) -> Dict[str, Any]:
    """Remove background from image via API."""
    try:
        if not bg_removal_service:
            raise HTTPException(status_code=503, detail="Services not initialized")

        # Get file object from file monitor service
        file_obj = await get_file_from_monitor(request.file_id)
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

        # Update status to processing
        await update_file_status(request.file_id, "processing", "Starting background removal")

        # Process the image
        result = bg_removal_service.remove_background(file_obj, bg_request)

        # Update file status based on result
        if result.success:
            await update_file_status(
                request.file_id,
                "awaiting_review",
                "Background removal completed",
                str(result.output_path) if result.output_path else None
            )
        else:
            await update_file_status(
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
        # Update status to failed
        try:
            await update_file_status(request.file_id, "failed", str(e))
        except:
            pass
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
            },
            "models_loaded": len(bg_removal_service.models_cache) if bg_removal_service else 0,
            "file_monitor_url": FILE_MONITOR_URL
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