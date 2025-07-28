# ===== src/services/processor_server.py =====
"""
Image Processor Server - Clean Architecture Implementation
Provides REST API for PSD processing and production format generation
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path

import uvicorn
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from ..config.settings import settings
from ..services.image_processing_service import ImageProcessingService
from ..services.filemaker_service import FileMakerService
from ..models.processing_models import FormatGenerationRequest
from ..models.metadata_models import ExifMetadata
from ..models.file_models import ProcessedFile, FileMetadata, FileType, FileStatus
from ..utils.logging_config import setup_logging

# Setup logging
setup_logging(settings.log_level)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="Crown Automotive Image Processor",
    description="PSD processing and production format generation",
    version="1.0.0"
)

# Global services
image_processor: Optional[ImageProcessingService] = None
filemaker: Optional[FileMakerService] = None

# File monitor service URL
FILE_MONITOR_URL = "http://file_monitor:8002"


class ProcessingRequestAPI(BaseModel):
    """API request model for processing operations."""
    file_id: str
    processing_type: str = "format_generation"
    output_formats: Optional[List[str]] = None
    include_watermark: bool = False
    include_brand_icon: bool = False


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


async def update_file_status(file_id: str, status: str, reason: str = None) -> bool:
    """Update file status via file monitor API."""
    try:
        async with httpx.AsyncClient() as client:
            data = {"status": status}
            if reason:
                data["reason"] = reason

            response = await client.put(f"{FILE_MONITOR_URL}/files/{file_id}/status",
                                        params=data)

            return response.status_code == 200

    except Exception as e:
        logger.error(f"Error updating file status: {e}")
        return False


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    global image_processor, filemaker

    try:
        logger.info("Initializing image processor services...")
        image_processor = ImageProcessingService()
        filemaker = FileMakerService()
        logger.info("Image processor services initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
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
            "image_processor": image_processor is not None,
            "file_monitor_api": file_monitor_healthy,
            "filemaker": filemaker is not None and filemaker.test_connection() if filemaker else False
        }
    }


@app.post("/process")
async def process_image(request: ProcessingRequestAPI) -> Dict[str, Any]:
    """Process image file into production formats."""
    try:
        if not image_processor or not filemaker:
            raise HTTPException(status_code=503, detail="Services not initialized")

        # Get file object from file monitor service
        file_obj = await get_file_from_monitor(request.file_id)
        if not file_obj:
            raise HTTPException(status_code=404, detail=f"File not found: {request.file_id}")

        # Determine output formats
        output_formats = request.output_formats
        if not output_formats:
            # Use all available formats
            output_formats = [spec['name'] for spec in image_processor.output_specs]

        # Get part metadata for EXIF
        exif_metadata = None
        if file_obj.part_number:
            part_metadata = filemaker.get_part_metadata(file_obj.part_number)
            if part_metadata:
                exif_metadata = ExifMetadata(part_metadata=part_metadata)

        # Create processing request
        format_request = FormatGenerationRequest(
            file_id=request.file_id,
            output_formats=output_formats,
            include_watermark=request.include_watermark,
            include_brand_icon=request.include_brand_icon
        )

        # Update status to processing
        await update_file_status(request.file_id, "processing")

        # Process formats
        result = image_processor.generate_formats(file_obj, format_request, exif_metadata)

        # Update status based on result
        if result.success:
            await update_file_status(
                request.file_id,
                "approved",
                f"Generated {result.metadata['successful_formats']} formats"
            )
        else:
            await update_file_status(
                request.file_id,
                "failed",
                "Format generation failed"
            )

        return {
            "success": result.success,
            "message": "Processing completed" if result.success else result.error_message,
            "file_id": request.file_id,
            "processing_time": result.processing_time_seconds,
            "formats_generated": result.metadata.get('successful_formats', 0),
            "failed_formats": result.metadata.get('failed_formats', [])
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Processing error: {e}")
        # Update status to failed
        try:
            await update_file_status(request.file_id, "failed", str(e))
        except:
            pass
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/formats")
async def list_output_formats():
    """List available output formats."""
    try:
        if not image_processor:
            raise HTTPException(status_code=503, detail="Image processor not initialized")

        formats = []
        for spec in image_processor.output_specs:
            formats.append({
                "name": spec["name"],
                "format": spec["format"],
                "dpi": spec["dpi"],
                "dimensions": spec.get("resize") or spec.get("extent"),
                "has_watermark": bool(spec.get("watermark")),
                "has_brand_icon": bool(spec.get("brand_icon"))
            })

        return {
            "total_formats": len(formats),
            "formats": formats
        }

    except Exception as e:
        logger.error(f"List formats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/status")
async def get_status():
    """Get detailed processor status."""
    try:
        if not image_processor:
            return {"status": "not_initialized"}

        return {
            "status": "running",
            "formats_available": len(image_processor.output_specs),
            "database_connected": filemaker.test_connection() if filemaker else False,
            "file_monitor_url": FILE_MONITOR_URL,
            "last_check": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Status error: {e}")
        return {"status": "error", "error": str(e)}


def main():
    """Main entry point."""
    logger.info("Starting Crown Automotive Image Processor...")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8003,
        log_level="info",
        access_log=True
    )


if __name__ == "__main__":
    main()