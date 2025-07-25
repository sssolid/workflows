#!/usr/bin/env python3
"""
File Monitor Server for Crown Automotive Image Processing
Provides REST API for file monitoring and change detection
"""

import os
import sys
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
import structlog

# Add utils to path
sys.path.append('/scripts/utils')

# Import the file monitor
sys.path.append('/scripts')
from file_monitor import FileMonitor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = structlog.get_logger(__name__)

# FastAPI app
app = FastAPI(
    title="Crown Automotive File Monitor",
    description="File monitoring and change detection for image processing",
    version="1.0.0"
)

# Global file monitor instance
file_monitor = None


class FileChangeResponse(BaseModel):
    """Response model for file changes"""
    timestamp: str
    scan_directory: str
    new_files_count: int
    new_files: List[Dict[str, Any]]
    total_monitored: int


@app.on_event("startup")
async def startup_event():
    """Initialize file monitor on startup"""
    global file_monitor

    try:
        watch_dir = '/data/input'
        state_file = '/data/metadata/file_monitor_state.json'

        file_monitor = FileMonitor(watch_dir, state_file)
        logger.info(f"File monitor initialized, watching: {watch_dir}")

    except Exception as e:
        logger.error(f"Failed to initialize file monitor: {e}")
        raise


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "monitoring": file_monitor.watch_dir if file_monitor else None
    }


@app.get("/scan", response_model=FileChangeResponse)
async def scan_for_changes():
    """Scan for new files and return changes"""
    try:
        if not file_monitor:
            raise Exception("File monitor not initialized")

        result = file_monitor.run_single_scan()

        return FileChangeResponse(
            timestamp=result["timestamp"],
            scan_directory=result["scan_directory"],
            new_files_count=result["new_files_count"],
            new_files=result["new_files"],
            total_monitored=result["total_monitored"]
        )

    except Exception as e:
        logger.error(f"Scan error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/smart_scan", response_model=FileChangeResponse)
async def smart_scan_for_processing():
    """Smart scan for files that need processing (regardless of state)"""
    try:
        if not file_monitor:
            raise Exception("File monitor not initialized")

        result = file_monitor.run_smart_scan()

        return FileChangeResponse(
            timestamp=result["timestamp"],
            scan_directory=result["scan_directory"],
            new_files_count=result["processable_files_count"],
            new_files=result["new_files"],
            total_monitored=result["total_monitored"]
        )

    except Exception as e:
        logger.error(f"Smart scan error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/status")
async def get_status():
    """Get detailed monitor status"""
    try:
        if not file_monitor:
            return {"status": "not_initialized"}

        # Get directory stats
        watch_path = Path(file_monitor.watch_dir)
        total_files = 0
        if watch_path.exists():
            total_files = len([f for f in watch_path.iterdir() if f.is_file()])

        return {
            "status": "running",
            "watch_directory": str(file_monitor.watch_dir),
            "state_file": str(file_monitor.state_file),
            "total_files_in_directory": total_files,
            "monitored_files": len(file_monitor.previous_files),
            "last_scan": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Status error: {e}")
        return {"status": "error", "error": str(e)}


@app.post("/reset")
async def reset_monitor():
    """Reset file monitor state"""
    try:
        if file_monitor:
            file_monitor.previous_files = set()
            if file_monitor.state_file.exists():
                file_monitor.state_file.unlink()

            return {"status": "reset", "message": "File monitor state cleared"}
        else:
            return {"status": "error", "message": "File monitor not initialized"}

    except Exception as e:
        logger.error(f"Reset error: {e}")
        return {"status": "error", "error": str(e)}


@app.get("/files")
async def list_files():
    """List all files in watch directory"""
    try:
        if not file_monitor:
            raise Exception("File monitor not initialized")

        watch_path = Path(file_monitor.watch_dir)
        if not watch_path.exists():
            return {"files": [], "total": 0}

        files = []
        for file_path in watch_path.iterdir():
            if file_path.is_file():
                stat = file_path.stat()
                files.append({
                    "name": file_path.name,
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "extension": file_path.suffix.lower()
                })

        # Sort by modification time
        files.sort(key=lambda x: x['modified'], reverse=True)

        return {
            "files": files,
            "total": len(files),
            "directory": str(watch_path)
        }

    except Exception as e:
        logger.error(f"List files error: {e}")
        return {"files": [], "total": 0, "error": str(e)}


if __name__ == "__main__":
    # Run the server
    uvicorn.run(
        "monitor_server:app",
        host="0.0.0.0",
        port=8002,
        log_level="info",
        access_log=True
    )