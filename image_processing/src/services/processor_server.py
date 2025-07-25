# ===== src/services/processor_server.py =====
"""
Image Processor Server - Clean Architecture Implementation
Provides REST API for PSD processing and production format generation
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional, List

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from ..config.settings import settings
from ..services.image_processing_service import ImageProcessingService
from ..services.file_monitor_service import FileMonitorService
from ..services.filemaker_service import FileMakerService
from ..models.processing_models import FormatGenerationRequest
from ..models.metadata_models import ExifMetadata
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
file_monitor: Optional[FileMonitorService] = None
filemaker: Optional[FileMakerService] = None


class ProcessingRequestAPI(BaseModel):
    """API request model for processing operations."""
    file_id: str
    processing_type: str = "format_generation"
    output_formats: Optional[List[str]] = None
    include_watermark: bool = False
    include_brand_icon: bool = False


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    global image_processor, file_monitor, filemaker

    try:
        logger.info("Initializing image processor services...")
        image_processor = ImageProcessingService()
        file_monitor = FileMonitorService()
        filemaker = FileMakerService()
        logger.info("Image processor services initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        raise


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "image_processor": image_processor is not None,
            "file_monitor": file_monitor is not None,
            "filemaker": filemaker is not None and filemaker.test_connection()
        }
    }


@app.post("/process")
async def process_image(request: ProcessingRequestAPI) -> Dict[str, Any]:
    """Process image file into production formats."""
    try:
        if not all([image_processor, file_monitor, filemaker]):
            raise HTTPException(status_code=503, detail="Services not initialized")

        # Get file object
        file_obj = file_monitor.get_file_by_id(request.file_id)
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
        file_monitor.update_file_status(request.file_id, "processing")

        # Process formats
        result = image_processor.generate_formats(file_obj, format_request, exif_metadata)

        # Update status based on result
        if result.success:
            file_monitor.update_file_status(
                request.file_id,
                "approved",
                f"Generated {result.metadata['successful_formats']} formats"
            )
        else:
            file_monitor.update_file_status(
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