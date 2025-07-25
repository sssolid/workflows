#!/usr/bin/env python3
"""
Image Processor Server for Crown Automotive
Provides REST API for PSD processing and production format generation
"""

import os
import sys
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
import structlog

# Add utils to path
sys.path.append('/scripts/utils')

# Import the image processor
sys.path.append('/scripts')
from image_processor import ImageProcessor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = structlog.get_logger(__name__)

# FastAPI app
app = FastAPI(
    title="Crown Automotive Image Processor",
    description="PSD processing and production format generation",
    version="1.0.0"
)

# Global processor instance
image_processor = None


class ProcessingRequest(BaseModel):
    """Request model for image processing"""
    file_path: str
    source_type: str = "auto"  # auto, psd, background_removed
    output_formats: Optional[List[str]] = None


class ProcessingResponse(BaseModel):
    """Response model for processing operations"""
    success: bool
    message: str
    base_name: str
    processing_time: float
    formats_generated: int
    output_paths: List[str]
    metadata: Dict[str, Any]


@app.on_event("startup")
async def startup_event():
    """Initialize image processor on startup"""
    global image_processor

    try:
        image_processor = ImageProcessor()
        logger.info("Image processor initialized successfully")

    except Exception as e:
        logger.error(f"Failed to initialize image processor: {e}")
        raise


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "processor_ready": image_processor is not None
    }


@app.post("/process", response_model=ProcessingResponse)
async def process_image(request: ProcessingRequest):
    """Process image file into production formats"""
    try:
        if not image_processor:
            raise Exception("Image processor not initialized")

        file_path = Path(request.file_path)
        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {file_path}")

        # Process the image
        result = image_processor.process_single_file(file_path, request.source_type)

        # Extract output paths from successful variants
        output_paths = [variant["path"] for variant in result.get("variants", [])]

        return ProcessingResponse(
            success=len(result.get("failed_variants", [])) == 0,
            message="Processing completed successfully" if len(
                result.get("failed_variants", [])) == 0 else "Processing completed with some failures",
            base_name=result["base_name"],
            processing_time=result["processing_time_seconds"],
            formats_generated=result["successful_variants"],
            output_paths=output_paths,
            metadata=result
        )

    except Exception as e:
        logger.error(f"Processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/process_batch")
async def process_batch(file_paths: List[str]):
    """Process multiple files"""
    try:
        if not image_processor:
            raise Exception("Image processor not initialized")

        # Convert strings to Path objects
        path_objects = []
        for file_path in file_paths:
            path_obj = Path(file_path)
            if not path_obj.exists():
                logger.warning(f"File not found: {file_path}")
                continue
            path_objects.append(path_obj)

        if not path_objects:
            raise HTTPException(status_code=400, detail="No valid files found")

        # Process the batch
        results = image_processor.process_batch(path_objects)

        return {
            "processed_count": len(results),
            "results": results
        }

    except Exception as e:
        logger.error(f"Batch processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/formats")
async def list_output_formats():
    """List available output formats"""
    try:
        if not image_processor:
            raise Exception("Image processor not initialized")

        formats = []
        for spec in image_processor.specs:
            formats.append({
                "name": spec["name"],
                "format": spec["format"],
                "dpi": spec["dpi"],
                "dimensions": spec.get("resize") or spec.get("extent"),
                "background": spec.get("background"),
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


@app.get("/metadata/{part_number}")
async def get_part_metadata(part_number: str):
    """Get metadata for a specific part number"""
    try:
        if not image_processor:
            raise Exception("Image processor not initialized")

        metadata = image_processor.get_part_metadata(part_number)

        if metadata:
            return {"part_number": part_number, "metadata": metadata}
        else:
            raise HTTPException(status_code=404, detail=f"No metadata found for part: {part_number}")

    except Exception as e:
        logger.error(f"Metadata lookup error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/database/test")
async def test_database_connection():
    """Test FileMaker database connection"""
    try:
        if not image_processor:
            raise Exception("Image processor not initialized")

        # Test by trying to fetch metadata
        metadata_count = len(image_processor.part_metadata)

        return {
            "database_connected": metadata_count > 0,
            "parts_loaded": metadata_count,
            "test_time": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Database test error: {e}")
        return {
            "database_connected": False,
            "error": str(e),
            "test_time": datetime.now().isoformat()
        }


@app.get("/status")
async def get_status():
    """Get detailed processor status"""
    try:
        if not image_processor:
            return {"status": "not_initialized"}

        return {
            "status": "running",
            "formats_available": len(image_processor.specs),
            "parts_metadata_loaded": len(image_processor.part_metadata),
            "database_connected": len(image_processor.part_metadata) > 0,
            "last_check": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Status error: {e}")
        return {"status": "error", "error": str(e)}


@app.post("/reload")
async def reload_configuration():
    """Reload configuration and metadata"""
    try:
        global image_processor

        # Reinitialize the processor
        image_processor = ImageProcessor()

        return {
            "status": "reloaded",
            "formats_loaded": len(image_processor.specs),
            "parts_loaded": len(image_processor.part_metadata),
            "reload_time": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Reload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    # Run the server
    uvicorn.run(
        "processor_server:app",
        host="0.0.0.0",
        port=8003,
        log_level="info",
        access_log=True
    )