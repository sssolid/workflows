#!/usr/bin/env python3
"""
Web Server for Image Processing System
Serves processed images and provides review interface for marketing team
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
import asyncio
import uuid
from urllib.parse import unquote, quote

import aiohttp
from aiohttp import web, hdrs
import aiofiles
from jinja2 import Environment, FileSystemLoader
import structlog

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/data/logs/web_server.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
TEMPLATES_DIR = Path('/templates')
ASSETS_DIR = Path('/assets')
DATA_DIR = Path('/data')
PROCESSING_DIR = DATA_DIR / 'processing'
PRODUCTION_DIR = DATA_DIR / 'production'
DECISIONS_DIR = DATA_DIR / 'decisions'
METADATA_DIR = DATA_DIR / 'metadata'

# Server configuration
SERVER_HOST = os.getenv('IMAGE_SERVER_HOST', '0.0.0.0')
SERVER_PORT = int(os.getenv('IMAGE_SERVER_PORT', '8080'))

PUBLIC_SERVER_HOST = os.getenv('IMAGE_SERVER_PUBLIC_HOST', '0.0.0.0')
PUBLIC_SERVER_PORT = int(os.getenv('IMAGE_SERVER_PUBLIC_PORT', '8080'))


class ImageServer:
    def __init__(self):
        self.app = web.Application()
        self.setup_routes()
        self.jinja_env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))

        # Ensure directories exist
        for directory in [DECISIONS_DIR, METADATA_DIR]:
            directory.mkdir(parents=True, exist_ok=True)

    def setup_routes(self):
        """Setup all web routes"""

        # Static file serving
        self.app.router.add_get('/', self.dashboard)
        self.app.router.add_get('/health', self.health_check)

        # Image serving routes
        self.app.router.add_get('/originals/{filename}', self.serve_original)
        self.app.router.add_get('/bg_removed/{filename}', self.serve_bg_removed)
        self.app.router.add_get('/production/{format}/{filename}', self.serve_production)
        self.app.router.add_get('/browse/{path:.*}', self.browse_files)

        # Review interface
        self.app.router.add_get('/review/{filename}', self.review_interface)
        self.app.router.add_get('/exif/{filename}', self.exif_viewer)

        # API endpoints
        self.app.router.add_get('/api/status', self.api_status)
        self.app.router.add_post('/api/decision', self.api_decision)
        self.app.router.add_get('/api/files/pending', self.api_pending_files)
        self.app.router.add_get('/api/files/completed', self.api_completed_files)
        self.app.router.add_get('/api/metadata/{filename}', self.api_file_metadata)

        # Decision API endpoints
        self.app.router.add_get('/api/decisions/pending', self.api_pending_decisions)
        self.app.router.add_get('/api/decisions/check', self.api_check_decisions)

        # EXIF editing
        self.app.router.add_post('/api/exif/update', self.api_update_exif)

        # Static assets
        self.app.router.add_static('/assets/', ASSETS_DIR)

        # Enable CORS for local network access
        self.app.middlewares.append(self.cors_handler)

    @web.middleware
    async def cors_handler(self, request, handler):
        """Add CORS headers for local network access"""
        response = await handler(request)
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response

    def clean_filename(self, filename: str) -> str:
        """Clean and decode filename for file system operations"""
        # URL decode the filename
        decoded = unquote(filename)
        return decoded

    def get_base_filename(self, filename: str) -> str:
        """Get the base filename without _bg_removed suffix"""
        clean_name = self.clean_filename(filename)
        base_name = clean_name.replace('_bg_removed', '')
        # Remove extension for base name
        return Path(base_name).stem

    def find_original_file(self, filename: str) -> Optional[Path]:
        """Find the original file for a given filename"""
        clean_name = self.clean_filename(filename)
        base_name = self.get_base_filename(clean_name)

        # Try different locations and extensions
        search_paths = [
            PROCESSING_DIR / 'originals',
            DATA_DIR / 'input'
        ]

        extensions = ['.psd', '.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp']

        for search_dir in search_paths:
            if not search_dir.exists():
                continue

            # Try exact match first
            for ext in extensions:
                potential_file = search_dir / f"{base_name}{ext}"
                if potential_file.exists():
                    return potential_file

            # Try case-insensitive search
            try:
                for file_path in search_dir.iterdir():
                    if file_path.is_file():
                        file_base = file_path.stem.upper()
                        if file_base == base_name.upper():
                            return file_path
            except Exception as e:
                logger.warning(f"Error searching in {search_dir}: {e}")

        return None

    def find_bg_removed_file(self, filename: str) -> Optional[Path]:
        """Find the background removed file for a given filename"""
        clean_name = self.clean_filename(filename)
        base_name = self.get_base_filename(clean_name)

        bg_removed_dir = PROCESSING_DIR / 'bg_removed'
        if not bg_removed_dir.exists():
            return None

        # Try exact match first
        potential_file = bg_removed_dir / f"{base_name}_bg_removed.png"
        if potential_file.exists():
            return potential_file

        # Try case-insensitive search
        try:
            for file_path in bg_removed_dir.iterdir():
                if file_path.is_file() and file_path.suffix.lower() == '.png':
                    file_base = file_path.stem.upper().replace('_BG_REMOVED', '')
                    if file_base == base_name.upper():
                        return file_path
        except Exception as e:
            logger.warning(f"Error searching for bg_removed file: {e}")

        return None

    async def health_check(self, request):
        """Health check endpoint"""
        return web.json_response({
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "server": "image_processing_server"
        })

    async def dashboard(self, request):
        """Main dashboard interface"""
        try:
            template = self.jinja_env.get_template('dashboard.html')

            # Get current status
            pending_files = await self.get_pending_files()
            completed_files = await self.get_completed_files()

            context = {
                "server_url": f"http://{PUBLIC_SERVER_HOST}:{PUBLIC_SERVER_PORT}",
                "pending_count": len(pending_files),
                "completed_count": len(completed_files),
                "pending_files": pending_files[:10],  # Latest 10
                "completed_files": completed_files[:10],  # Latest 10
                "timestamp": datetime.now().isoformat()
            }

            html_content = template.render(context)
            return web.Response(text=html_content, content_type='text/html')

        except Exception as e:
            logger.error(f"Error rendering dashboard: {e}")
            return web.Response(text=f"Dashboard error: {e}", status=500)

    async def serve_original(self, request):
        """Serve original image files"""
        filename = request.match_info['filename']

        file_path = self.find_original_file(filename)
        if file_path:
            return await self.serve_file(file_path)
        else:
            logger.warning(f"Original file not found: {filename}")
            return web.Response(status=404, text="Original file not found")

    async def serve_bg_removed(self, request):
        """Serve background-removed image files"""
        filename = request.match_info['filename']

        file_path = self.find_bg_removed_file(filename)
        if file_path:
            return await self.serve_file(file_path)
        else:
            logger.warning(f"Background removed file not found: {filename}")
            return web.Response(status=404, text="Background removed file not found")

    async def serve_production(self, request):
        """Serve production format files"""
        format_name = request.match_info['format']
        filename = request.match_info['filename']

        clean_filename = self.clean_filename(filename)
        file_path = PRODUCTION_DIR / format_name / clean_filename

        return await self.serve_file(file_path)

    async def serve_file(self, file_path: Path):
        """Generic file serving with proper headers"""
        try:
            if not file_path.exists():
                return web.Response(status=404, text="File not found")

            # Determine content type
            content_type = 'application/octet-stream'
            if file_path.suffix.lower() in ['.png']:
                content_type = 'image/png'
            elif file_path.suffix.lower() in ['.jpg', '.jpeg']:
                content_type = 'image/jpeg'
            elif file_path.suffix.lower() in ['.tiff', '.tif']:
                content_type = 'image/tiff'
            elif file_path.suffix.lower() in ['.psd']:
                content_type = 'application/octet-stream'

            # Read and serve file
            async with aiofiles.open(file_path, 'rb') as f:
                content = await f.read()

            response = web.Response(body=content, content_type=content_type)
            response.headers['Cache-Control'] = 'max-age=3600'  # 1 hour cache
            return response

        except Exception as e:
            logger.error(f"Error serving file {file_path}: {e}")
            return web.Response(status=500, text="Server error")

    async def browse_files(self, request):
        """File browser for production files"""
        path = request.match_info.get('path', '')
        browse_path = PRODUCTION_DIR / path

        try:
            if not browse_path.exists() or not browse_path.is_dir():
                return web.Response(status=404, text="Directory not found")

            files = []
            for item in browse_path.iterdir():
                if item.is_file() and item.suffix.lower() in ['.png', '.jpg', '.jpeg', '.tiff', '.tif']:
                    stat = item.stat()
                    files.append({
                        "name": item.name,
                        "size": stat.st_size,
                        "size_mb": round(stat.st_size / (1024 * 1024), 2),
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "url": f"/production/{path}/{quote(item.name)}" if path else f"/production/{quote(item.name)}"
                    })

            # Sort by modification time (newest first)
            files.sort(key=lambda x: x['modified'], reverse=True)

            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>File Browser - {path or 'Production Files'}</title>
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 20px; }}
                    .file-list {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 15px; }}
                    .file-item {{ border: 1px solid #ddd; padding: 10px; border-radius: 8px; text-align: center; }}
                    .file-item img {{ max-width: 100%; height: 150px; object-fit: cover; border-radius: 4px; }}
                    .file-name {{ font-weight: bold; margin: 10px 0 5px 0; }}
                    .file-info {{ font-size: 0.8em; color: #666; }}
                    .download-btn {{ background: #007acc; color: white; padding: 8px 16px; text-decoration: none; border-radius: 4px; display: inline-block; margin-top: 10px; }}
                </style>
            </head>
            <body>
                <h1>Production Files - {path or 'All Formats'}</h1>
                <p>{len(files)} files found</p>
                <div class="file-list">
            """

            for file in files:
                html_content += f"""
                    <div class="file-item">
                        <img src="{file['url']}" alt="{file['name']}" onerror="this.style.display='none'">
                        <div class="file-name">{file['name']}</div>
                        <div class="file-info">{file['size_mb']} MB</div>
                        <a href="{file['url']}" class="download-btn" download>Download</a>
                    </div>
                """

            html_content += """
                </div>
            </body>
            </html>
            """

            return web.Response(text=html_content, content_type='text/html')

        except Exception as e:
            logger.error(f"Error browsing files: {e}")
            return web.Response(status=500, text="Browse error")

    async def review_interface(self, request):
        """Image review interface for background removal approval"""
        filename = request.match_info['filename']
        clean_filename = self.clean_filename(filename)

        try:
            # Get file metadata
            metadata = await self.get_file_metadata(clean_filename)

            template = self.jinja_env.get_template('review.html')

            context = {
                "filename": clean_filename,
                "server_url": f"http://{PUBLIC_SERVER_HOST}:{PUBLIC_SERVER_PORT}",
                "metadata": metadata,
                "timestamp": datetime.now().isoformat()
            }

            html_content = template.render(context)
            return web.Response(text=html_content, content_type='text/html')

        except Exception as e:
            logger.error(f"Error rendering review interface: {e}")
            return web.Response(text=f"Review interface error: {e}", status=500)

    async def exif_viewer(self, request):
        """EXIF data viewer and editor"""
        filename = request.match_info['filename']
        clean_filename = self.clean_filename(filename)

        try:
            # Get EXIF data for the file
            exif_data = await self.get_exif_data(clean_filename)

            template = self.jinja_env.get_template('exif_editor.html')

            context = {
                "filename": clean_filename,
                "exif_data": exif_data,
                "server_url": f"http://{PUBLIC_SERVER_HOST}:{PUBLIC_SERVER_PORT}",
                "timestamp": datetime.now().isoformat()
            }

            html_content = template.render(context)
            return web.Response(text=html_content, content_type='text/html')

        except Exception as e:
            logger.error(f"Error rendering EXIF viewer: {e}")
            return web.Response(text=f"EXIF viewer error: {e}", status=500)

    async def api_status(self, request):
        """API endpoint for system status"""
        try:
            pending_files = await self.get_pending_files()
            completed_files = await self.get_completed_files()

            status = {
                "server": "running",
                "timestamp": datetime.now().isoformat(),
                "processing": 0,  # Would need to implement processing queue tracking
                "pending": len(pending_files),
                "completed": len(completed_files),
                "failed": 0  # Would need to implement failure tracking
            }

            return web.json_response(status)

        except Exception as e:
            logger.error(f"Error getting status: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def api_decision(self, request):
        """API endpoint for approval/rejection decisions"""
        try:
            data = await request.json()

            action = data.get('action')  # 'approve', 'reject', 'retry'
            file_id = data.get('fileId') or data.get('file')

            if not action or not file_id:
                return web.json_response({"error": "Missing action or fileId"}, status=400)

            # Clean the file_id
            clean_file_id = self.clean_filename(file_id)

            # Create decision record
            decision_id = str(uuid.uuid4())
            decision_data = {
                "decision_id": decision_id,
                "action": action,
                "file_id": clean_file_id,
                "timestamp": datetime.now().isoformat(),
                "ip_address": request.remote,
                "user_agent": request.headers.get('User-Agent', '')
            }

            # Save decision to file for n8n to pick up
            decision_file = DECISIONS_DIR / f"{clean_file_id}_{decision_id}.json"

            async with aiofiles.open(decision_file, 'w') as f:
                await f.write(json.dumps(decision_data, indent=2))

            logger.info(f"Decision recorded: {action} for {clean_file_id}")

            return web.json_response({
                "status": "success",
                "decision_id": decision_id,
                "action": action,
                "file_id": clean_file_id
            })

        except Exception as e:
            logger.error(f"Error recording decision: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def api_pending_files(self, request):
        """API endpoint for pending files"""
        try:
            pending_files = await self.get_pending_files()
            return web.json_response(pending_files)
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    async def api_completed_files(self, request):
        """API endpoint for completed files"""
        try:
            completed_files = await self.get_completed_files()
            return web.json_response(completed_files)
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    async def api_file_metadata(self, request):
        """API endpoint for file metadata"""
        filename = request.match_info['filename']
        clean_filename = self.clean_filename(filename)
        try:
            metadata = await self.get_file_metadata(clean_filename)
            return web.json_response(metadata)
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    async def api_pending_decisions(self, request):
        """API endpoint for checking pending decisions"""
        try:
            decision_dir = DECISIONS_DIR

            if not decision_dir.exists():
                return web.json_response({"decisions": [], "count": 0})

            # Get decision files
            decision_files = list(decision_dir.glob("*.json"))

            if not decision_files:
                return web.json_response({"decisions": [], "count": 0})

            # Process up to 10 decisions at a time
            decisions = []
            processed_files = []

            for decision_file in decision_files[:10]:
                try:
                    async with aiofiles.open(decision_file, 'r') as f:
                        content = await f.read()
                        decision_data = json.loads(content)

                    decisions.append({
                        "decision_file": str(decision_file),
                        "action": decision_data.get("action"),
                        "file_id": decision_data.get("file_id"),
                        "timestamp": decision_data.get("timestamp"),
                        "decision_id": decision_data.get("decision_id")
                    })

                    # Mark for deletion
                    processed_files.append(decision_file)

                except Exception as e:
                    logger.error(f"Error processing decision file {decision_file}: {e}")
                    continue

            # Delete processed files
            for file_path in processed_files:
                try:
                    file_path.unlink()
                except Exception as e:
                    logger.error(f"Error deleting decision file {file_path}: {e}")

            return web.json_response({
                "decisions": decisions,
                "count": len(decisions),
                "processed": len(processed_files)
            })

        except Exception as e:
            logger.error(f"Error checking pending decisions: {e}")
            return web.json_response({"decisions": [], "count": 0, "error": str(e)})

    async def api_check_decisions(self, request):
        """Quick check for any pending decisions"""
        try:
            decision_dir = DECISIONS_DIR

            if not decision_dir.exists():
                return web.json_response({"has_decisions": False, "count": 0})

            decision_files = list(decision_dir.glob("*.json"))

            return web.json_response({
                "has_decisions": len(decision_files) > 0,
                "count": len(decision_files)
            })

        except Exception as e:
            logger.error(f"Error checking for decisions: {e}")
            return web.json_response({"has_decisions": False, "count": 0})

    async def api_update_exif(self, request):
        """API endpoint for updating EXIF data"""
        try:
            data = await request.json()
            filename = data.get('filename')
            exif_data = data.get('exif_data')

            if not filename or not exif_data:
                return web.json_response({"error": "Missing filename or exif_data"}, status=400)

            clean_filename = self.clean_filename(filename)

            # Update EXIF data (implementation depends on your EXIF editing requirements)
            result = await self.update_exif_data(clean_filename, exif_data)

            return web.json_response(result)

        except Exception as e:
            logger.error(f"Error updating EXIF data: {e}")
            return web.json_response({"error": str(e)}, status=500)

    # Helper methods
    async def get_pending_files(self) -> List[Dict[str, Any]]:
        """Get list of files pending review"""
        try:
            pending = []
            bg_removed_dir = PROCESSING_DIR / 'bg_removed'

            if bg_removed_dir.exists():
                for file_path in bg_removed_dir.iterdir():
                    if file_path.is_file() and file_path.suffix.lower() in ['.png', '.jpg', '.jpeg']:
                        stat = file_path.stat()
                        pending.append({
                            "filename": file_path.name,
                            "size_mb": round(stat.st_size / (1024 * 1024), 2),
                            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                            "preview_url": f"/bg_removed/{quote(file_path.name)}",
                            "review_url": f"/review/{quote(file_path.name)}"
                        })

            # Sort by modification time (newest first)
            pending.sort(key=lambda x: x['modified'], reverse=True)
            return pending

        except Exception as e:
            logger.error(f"Error getting pending files: {e}")
            return []

    async def get_completed_files(self) -> List[Dict[str, Any]]:
        """Get list of completed files"""
        try:
            completed = []

            # Look for processing logs to find completed files
            metadata_dir = METADATA_DIR

            if metadata_dir.exists():
                for log_file in metadata_dir.glob("*_processing_log.json"):
                    try:
                        async with aiofiles.open(log_file, 'r') as f:
                            content = await f.read()
                            log_data = json.loads(content)

                        if log_data.get("successful_variants", 0) > 0:
                            completed.append({
                                "filename": log_data.get("base_name", "unknown"),
                                "variants_count": log_data.get("successful_variants", 0),
                                "processing_time": log_data.get("processing_time_seconds", 0),
                                "timestamp": log_data.get("timestamp", ""),
                                "browse_url": "/browse/production/"
                            })
                    except Exception as e:
                        logger.error(f"Error reading log file {log_file}: {e}")
                        continue

            # Sort by timestamp (newest first)
            completed.sort(key=lambda x: x['timestamp'], reverse=True)
            return completed

        except Exception as e:
            logger.error(f"Error getting completed files: {e}")
            return []

    async def get_file_metadata(self, filename: str) -> Dict[str, Any]:
        """Get metadata for a specific file"""
        try:
            base_name = Path(filename).stem.replace('_bg_removed', '')

            # Try to find processing log
            log_file = METADATA_DIR / f"{base_name}_processing_log.json"
            bg_log_file = METADATA_DIR / f"{base_name}_bg_removal_log.json"

            metadata = {"filename": filename}

            if log_file.exists():
                async with aiofiles.open(log_file, 'r') as f:
                    content = await f.read()
                    metadata.update(json.loads(content))

            if bg_log_file.exists():
                async with aiofiles.open(bg_log_file, 'r') as f:
                    content = await f.read()
                    bg_data = json.loads(content)
                    metadata['background_removal'] = bg_data

            return metadata

        except Exception as e:
            logger.error(f"Error getting metadata for {filename}: {e}")
            return {"filename": filename, "error": str(e)}

    async def get_exif_data(self, filename: str) -> Dict[str, Any]:
        """Get EXIF data for a file"""
        # This would typically use exiftool or similar to extract EXIF data
        # For now, return placeholder data
        return {
            "filename": filename,
            "exif": {
                "Make": "Crown Automotive",
                "Model": "Product Image",
                "DateTime": datetime.now().isoformat(),
                "Software": "Crown Image Processing System"
            }
        }

    async def update_exif_data(self, filename: str, exif_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update EXIF data for a file"""
        # Implementation would use exiftool to update metadata
        # For now, return success response
        return {
            "status": "success",
            "filename": filename,
            "updated_fields": list(exif_data.keys())
        }


async def create_app():
    """Create and configure the web application"""
    server = ImageServer()
    return server.app


async def main():
    """Main entry point"""
    logger.info(f"Starting image server on {SERVER_HOST}:{SERVER_PORT}")

    app = await create_app()

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, SERVER_HOST, SERVER_PORT)
    await site.start()

    logger.info(f"Image server started at http://{SERVER_HOST}:{SERVER_PORT}")
    logger.info("Available endpoints:")
    logger.info("  - / : Main dashboard")
    logger.info("  - /review/{filename} : Image review interface")
    logger.info("  - /browse/production/ : File browser")
    logger.info("  - /api/status : System status")
    logger.info("  - /api/decisions/pending : Pending decisions for n8n")
    logger.info("  - /api/decisions/check : Quick decision check")

    try:
        await asyncio.Future()  # Run forever
    except KeyboardInterrupt:
        logger.info("Shutting down server...")
    finally:
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())