#!/usr/bin/env python3
"""
ML Processing Server for Crown Automotive Image Processing
Provides REST API for background removal and other ML operations
"""

import os
import sys
import logging
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
import tempfile
import shutil

import uvicorn
from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
import structlog

# Add utils to path
sys.path.append('/scripts/utils')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = structlog.get_logger(__name__)

# FastAPI app
app = FastAPI(
    title="Crown Automotive ML Processor",
    description="Background removal and ML processing for automotive parts",
    version="1.0.0"
)

# Global variables for ML models
bg_removal_session = None
model_cache = {}


class BackgroundRemovalRequest(BaseModel):
    """Request model for background removal"""
    input_path: str
    output_path: Optional[str] = None
    enhance_input: bool = True
    post_process: bool = True
    model_name: str = "isnet-general-use"


class ProcessingResponse(BaseModel):
    """Response model for processing operations"""
    success: bool
    message: str
    output_path: Optional[str] = None
    processing_time: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


def initialize_ml_models():
    """Initialize ML models on startup"""
    global bg_removal_session

    try:
        logger.info("Initializing background removal models...")
        from rembg import new_session

        # Initialize default model
        bg_removal_session = new_session("isnet-general-use")
        model_cache["isnet-general-use"] = bg_removal_session

        logger.info("ML models initialized successfully")

    except Exception as e:
        logger.error(f"Failed to initialize ML models: {e}")
        raise


def get_bg_removal_session(model_name: str = "isnet-general-use"):
    """Get or create background removal session"""
    global model_cache

    if model_name not in model_cache:
        try:
            from rembg import new_session
            logger.info(f"Loading model: {model_name}")
            model_cache[model_name] = new_session(model_name)
        except Exception as e:
            logger.error(f"Failed to load model {model_name}: {e}")
            # Fallback to default model
            if "isnet-general-use" in model_cache:
                return model_cache["isnet-general-use"]
            raise

    return model_cache[model_name]


# Use lifespan instead of deprecated on_event
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    try:
        logger.info("Starting ML server initialization...")
        initialize_ml_models()
        logger.info("ML server startup complete - ready to accept requests")
    except Exception as e:
        logger.error(f"Startup failed: {e}")
        raise

    yield

    # Shutdown
    logger.info("ML server shutting down...")


# Apply lifespan to app
app = FastAPI(
    title="Crown Automotive ML Processor",
    description="Background removal and ML processing for automotive parts",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    global bg_removal_session

    # Check if models are actually loaded
    models_ready = bg_removal_session is not None and len(model_cache) > 0

    if not models_ready:
        # Still initializing
        raise HTTPException(status_code=503, detail="Service starting up, models not ready yet")

    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "models_loaded": list(model_cache.keys()),
        "ready": True
    }


@app.get("/models")
async def list_models():
    """List available models"""
    available_models = [
        "isnet-general-use",
        "u2net",
        "u2netp",
        "u2net_human_seg",
        "silueta"
    ]

    return {
        "available_models": available_models,
        "loaded_models": list(model_cache.keys())
    }


@app.post("/remove_background", response_model=ProcessingResponse)
async def remove_background_api(request: BackgroundRemovalRequest):
    """Remove background from image via API"""
    try:
        start_time = datetime.now()

        # Validate input file
        input_path = Path(request.input_path)
        if not input_path.exists():
            raise HTTPException(status_code=404, detail=f"Input file not found: {input_path}")

        # FIXED: Always set output to processing directory
        if request.output_path:
            output_path = Path(request.output_path)
        else:
            # Force output to correct directory
            bg_removed_dir = Path('/data/processing/bg_removed')
            bg_removed_dir.mkdir(parents=True, exist_ok=True)
            output_path = bg_removed_dir / f"{input_path.stem}_bg_removed.png"

        logger.info(f"API Background removal: {input_path} -> {output_path}")

        # Get the appropriate model session
        session = get_bg_removal_session(request.model_name)

        # Import and use background removal logic
        from background_removal import BackgroundRemover

        # Create a temporary instance for processing
        remover = BackgroundRemover()
        remover.session = session
        remover.model_name = request.model_name

        # Process the image with FIXED output path
        result = remover.remove_background(
            input_path,
            output_path,  # Use the corrected output path
            enhance_input=request.enhance_input,
            post_process=request.post_process
        )

        processing_time = (datetime.now() - start_time).total_seconds()

        if result.get("status") == "success":
            return ProcessingResponse(
                success=True,
                message="Background removal completed successfully",
                output_path=str(output_path),
                processing_time=processing_time,
                metadata=result
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Background removal failed: {result.get('error', 'Unknown error')}"
            )

    except Exception as e:
        logger.error(f"Background removal API error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/remove_background_upload")
async def remove_background_upload(
        file: UploadFile = File(...),
        model_name: str = "isnet-general-use",
        enhance_input: bool = True,
        post_process: bool = True
):
    """Remove background from uploaded image file"""
    try:
        # Validate file type
        if not file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="File must be an image")

        # Create temporary files
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp_input:
            # Save uploaded file
            content = await file.read()
            tmp_input.write(content)
            tmp_input_path = tmp_input.name

        try:
            # Set up output path
            tmp_output_path = tmp_input_path.replace(Path(tmp_input_path).suffix, "_bg_removed.png")

            # Process using the API
            request = BackgroundRemovalRequest(
                input_path=tmp_input_path,
                output_path=tmp_output_path,
                model_name=model_name,
                enhance_input=enhance_input,
                post_process=post_process
            )

            result = await remove_background_api(request)

            if result.success and Path(tmp_output_path).exists():
                # Return the processed image
                return FileResponse(
                    tmp_output_path,
                    media_type="image/png",
                    filename=f"{Path(file.filename).stem}_bg_removed.png"
                )
            else:
                raise HTTPException(status_code=500, detail="Processing failed")

        finally:
            # Cleanup temporary files
            for tmp_file in [tmp_input_path, tmp_output_path]:
                if os.path.exists(tmp_file):
                    os.unlink(tmp_file)

    except Exception as e:
        logger.error(f"Upload processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/retry_background_removal", response_model=ProcessingResponse)
async def retry_background_removal(
        input_path: str,
        output_path: Optional[str] = None,
        alternative_model: str = "u2net"
):
    """Retry background removal with different settings"""
    try:
        # Try with different model and settings
        request = BackgroundRemovalRequest(
            input_path=input_path,
            output_path=output_path,
            model_name=alternative_model,
            enhance_input=False,  # Skip enhancement for retry
            post_process=True
        )

        return await remove_background_api(request)

    except Exception as e:
        logger.error(f"Retry background removal error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/status")
async def get_status():
    """Get detailed status information"""
    try:
        import torch
        import cv2
        from rembg import __version__ as rembg_version

        return {
            "service": "Crown Automotive ML Processor",
            "status": "running",
            "timestamp": datetime.now().isoformat(),
            "versions": {
                "torch": torch.__version__,
                "opencv": cv2.__version__,
                "rembg": rembg_version
            },
            "models": {
                "loaded": list(model_cache.keys()),
                "default": "isnet-general-use"
            },
            "system": {
                "cuda_available": torch.cuda.is_available() if 'torch' in locals() else False,
                "device_count": torch.cuda.device_count() if 'torch' in locals() and torch.cuda.is_available() else 0
            }
        }
    except Exception as e:
        logger.error(f"Status check error: {e}")
        return {
            "service": "Crown Automotive ML Processor",
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


@app.post("/preload_models")
async def preload_models(models: List[str] = None):
    """Preload specified models for faster processing"""
    try:
        if models is None:
            models = ["isnet-general-use", "u2net", "silueta"]

        loaded = []
        failed = []

        for model_name in models:
            try:
                get_bg_removal_session(model_name)
                loaded.append(model_name)
            except Exception as e:
                failed.append({"model": model_name, "error": str(e)})

        return {
            "loaded": loaded,
            "failed": failed,
            "total_loaded": len(model_cache)
        }

    except Exception as e:
        logger.error(f"Model preloading error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def cleanup_background_task():
    """Background task to clean up temporary files"""
    while True:
        try:
            # Clean up any temporary files older than 1 hour
            temp_dir = Path(tempfile.gettempdir())
            cutoff_time = datetime.now().timestamp() - 3600  # 1 hour ago

            for temp_file in temp_dir.glob("tmp*"):
                if temp_file.is_file() and temp_file.stat().st_mtime < cutoff_time:
                    try:
                        temp_file.unlink()
                    except OSError:
                        pass

            await asyncio.sleep(1800)  # Run every 30 minutes

        except Exception as e:
            logger.error(f"Cleanup task error: {e}")
            await asyncio.sleep(1800)


# Start background tasks on startup
@app.on_event("startup")
async def start_background_tasks():
    """Start background tasks"""
    asyncio.create_task(cleanup_background_task())


def main():
    """Main entry point with proper server binding"""
    logger.info("Starting Crown Automotive ML Processor...")
    logger.info("Server will bind to 0.0.0.0:8001 for container networking")

    uvicorn.run(
        app,  # Use app object directly
        host="0.0.0.0",  # CRITICAL: Bind to all interfaces for Docker
        port=8001,
        log_level="info",
        access_log=True,
        timeout_keep_alive=30,
        workers=1  # Single worker for model consistency
    )


if __name__ == "__main__":
    main()