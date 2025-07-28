# ===== src/services/monitor_server.py =====
"""
File Monitor Server - Clean Architecture Implementation
Provides REST API for file monitoring and change detection
"""

import logging
from datetime import datetime
from typing import List, Dict, Any

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from ..config.settings import settings
from ..services.file_monitor_service import FileMonitorService
from ..utils.logging_config import setup_logging

# Setup logging
setup_logging(settings.log_level)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="Crown Automotive File Monitor",
    description="File monitoring and change detection for image processing",
    version="1.0.0"
)

# Global file monitor instance
file_monitor: FileMonitorService = None


class FileChangeResponse(BaseModel):
    """Response model for file changes."""
    timestamp: str
    scan_directory: str
    new_files_count: int
    new_files: List[Dict[str, Any]]
    total_monitored: int


class FileDetailResponse(BaseModel):
    """Response model for file details."""
    file_id: str
    filename: str
    file_type: str
    size_mb: float
    status: str
    current_location: str
    part_number: str = None
    processing_history: List[Dict[str, Any]] = []
    checksum: str


@app.on_event("startup")
async def startup_event():
    """Initialize file monitor on startup."""
    global file_monitor

    try:
        logger.info("Initializing file monitor...")
        file_monitor = FileMonitorService()
        logger.info(f"File monitor initialized, watching: {file_monitor.input_dir}")
    except Exception as e:
        logger.error(f"Failed to initialize file monitor: {e}")
        raise


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "monitoring": str(file_monitor.input_dir) if file_monitor else None
    }


@app.get("/scan", response_model=FileChangeResponse)
async def scan_for_changes():
    """Scan for new files and return changes."""
    try:
        if not file_monitor:
            raise HTTPException(status_code=503, detail="File monitor not initialized")

        new_files = file_monitor.discover_new_files()

        return FileChangeResponse(
            timestamp=datetime.now().isoformat(),
            scan_directory=str(file_monitor.input_dir),
            new_files_count=len(new_files),
            new_files=[
                {
                    "file_id": f.metadata.file_id,
                    "filename": f.metadata.filename,
                    "file_type": f.metadata.file_type,
                    "size_mb": f.metadata.size_mb,
                    "is_psd": f.metadata.is_psd,
                    "path": str(f.current_location),
                    "checksum": f.metadata.checksum_sha256,
                    "status": f.metadata.status
                }
                for f in new_files
            ],
            total_monitored=len(file_monitor._tracked_files)
        )

    except Exception as e:
        logger.error(f"Scan error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/processable", response_model=FileChangeResponse)
async def get_processable_files():
    """Get files that need processing (including recovery from failures)."""
    try:
        if not file_monitor:
            raise HTTPException(status_code=503, detail="File monitor not initialized")

        # First recover any incomplete files
        recovered = file_monitor.scan_and_recover_incomplete()

        # Get all files needing processing
        processable_files = file_monitor.get_files_needing_processing()

        return FileChangeResponse(
            timestamp=datetime.now().isoformat(),
            scan_directory=str(file_monitor.input_dir),
            new_files_count=len(processable_files),
            new_files=[
                {
                    "file_id": f.metadata.file_id,
                    "filename": f.metadata.filename,
                    "file_type": f.metadata.file_type,
                    "size_mb": f.metadata.size_mb,
                    "is_psd": f.metadata.is_psd,
                    "path": str(f.current_location),
                    "status": f.metadata.status,
                    "checksum": f.metadata.checksum_sha256
                }
                for f in processable_files
            ],
            total_monitored=len(file_monitor._tracked_files)
        )

    except Exception as e:
        logger.error(f"Processable files error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/files/{file_id}", response_model=FileDetailResponse)
async def get_file_by_id(file_id: str):
    """Get detailed file information by ID."""
    try:
        if not file_monitor:
            raise HTTPException(status_code=503, detail="File monitor not initialized")

        file_obj = file_monitor.get_file_by_id(file_id)
        if not file_obj:
            raise HTTPException(status_code=404, detail=f"File not found: {file_id}")

        return FileDetailResponse(
            file_id=file_obj.metadata.file_id,
            filename=file_obj.metadata.filename,
            file_type=file_obj.metadata.file_type.value,
            size_mb=file_obj.metadata.size_mb,
            status=file_obj.metadata.status.value,
            current_location=str(file_obj.current_location) if file_obj.current_location else "",
            part_number=file_obj.part_number,
            processing_history=file_obj.processing_history,
            checksum=file_obj.metadata.checksum_sha256
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get file error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/files/{file_id}/status")
async def update_file_status(file_id: str, status: str, reason: str = None):
    """Update file status."""
    try:
        if not file_monitor:
            raise HTTPException(status_code=503, detail="File monitor not initialized")

        from ..models.file_models import FileStatus

        try:
            status_enum = FileStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

        success = file_monitor.update_file_status(file_id, status_enum, reason)

        if not success:
            raise HTTPException(status_code=404, detail=f"File not found: {file_id}")

        return {
            "success": True,
            "file_id": file_id,
            "new_status": status,
            "reason": reason,
            "timestamp": datetime.now().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Status update error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/files/{file_id}/part_number")
async def update_file_part_number(file_id: str, part_number: str, confidence: float = 1.0):
    """Update file part number."""
    try:
        if not file_monitor:
            raise HTTPException(status_code=503, detail="File monitor not initialized")

        success = file_monitor.add_file_part_number(file_id, part_number, confidence)

        if not success:
            raise HTTPException(status_code=404, detail=f"File not found: {file_id}")

        return {
            "success": True,
            "file_id": file_id,
            "part_number": part_number,
            "confidence": confidence,
            "timestamp": datetime.now().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Part number update error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/status")
async def get_status():
    """Get detailed monitor status."""
    try:
        if not file_monitor:
            return {"status": "not_initialized"}

        return {
            "status": "running",
            "watch_directory": str(file_monitor.input_dir),
            "state_file": str(file_monitor.state_file),
            "total_tracked_files": len(file_monitor._tracked_files),
            "last_scan": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Status error: {e}")
        return {"status": "error", "error": str(e)}


@app.post("/reset")
async def reset_monitor():
    """Reset file monitor state."""
    try:
        if file_monitor:
            file_monitor._tracked_files = {}
            if file_monitor.state_file.exists():
                file_monitor.state_file.unlink()

            return {"status": "reset", "message": "File monitor state cleared"}
        else:
            return {"status": "error", "message": "File monitor not initialized"}

    except Exception as e:
        logger.error(f"Reset error: {e}")
        return {"status": "error", "error": str(e)}


def main():
    """Main entry point."""
    logger.info("Starting Crown Automotive File Monitor...")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8002,
        log_level="info",
        access_log=True
    )


if __name__ == "__main__":
    main()