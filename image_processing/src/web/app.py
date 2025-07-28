# ===== src/web/app.py =====
"""
Web Application - Clean Architecture Implementation
Flask application with clean separation of concerns and manual override capabilities
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import httpx
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, flash
from werkzeug.utils import secure_filename

from ..config.settings import settings
from ..services.part_mapping_service import PartMappingService
from ..services.filemaker_service import FileMakerService
from ..services.notification_service import NotificationService
from ..models.file_models import FileStatus
from ..models.part_mapping_models import ManualOverride
from ..models.metadata_models import ExifMetadata, PartMetadata
from ..utils.logging_config import setup_logging

# Setup logging
setup_logging(settings.log_level)
logger = logging.getLogger(__name__)

# Service URLs
FILE_MONITOR_URL = "http://file_monitor:8002"


def create_app() -> Flask:
    """Create and configure Flask application."""
    app = Flask(__name__, template_folder='/app/templates')
    app.config['SECRET_KEY'] = settings.web.secret_key
    app.config['MAX_CONTENT_LENGTH'] = settings.processing.max_file_size_bytes

    # Initialize services (gracefully handle failures)
    part_mapper = None
    filemaker = None
    notifier = None

    try:
        part_mapper = PartMappingService()
        logger.info("Part mapping service initialized")
    except Exception as e:
        logger.warning(f"Part mapping service failed to initialize: {e}")

    try:
        filemaker = FileMakerService()
        logger.info("FileMaker service initialized")
    except Exception as e:
        logger.warning(f"FileMaker service failed to initialize: {e}")

    try:
        notifier = NotificationService()
        logger.info("Notification service initialized")
    except Exception as e:
        logger.warning(f"Notification service failed to initialize: {e}")

    async def get_files_by_status(status: str) -> List[Dict]:
        """Get files by status from file monitor service."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{FILE_MONITOR_URL}/processable")

                if response.status_code != 200:
                    logger.error(f"File monitor API error: {response.status_code}")
                    return []

                data = response.json()
                files = data.get('new_files', [])

                # Filter by status
                return [f for f in files if f.get('status') == status]

        except Exception as e:
            logger.error(f"Error getting files by status: {e}")
            return []

    async def get_file_by_id(file_id: str) -> Optional[Dict]:
        """Get file by ID from file monitor service."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{FILE_MONITOR_URL}/files/{file_id}")

                if response.status_code == 404:
                    return None
                elif response.status_code != 200:
                    logger.error(f"File monitor API error: {response.status_code}")
                    return None

                return response.json()

        except Exception as e:
            logger.error(f"Error getting file by ID: {e}")
            return None

    async def update_file_status_api(file_id: str, status: str, reason: str = None) -> bool:
        """Update file status via API."""
        try:
            async with httpx.AsyncClient() as client:
                params = {"status": status}
                if reason:
                    params["reason"] = reason

                response = await client.put(f"{FILE_MONITOR_URL}/files/{file_id}/status",
                                            params=params)

                return response.status_code == 200

        except Exception as e:
            logger.error(f"Error updating file status: {e}")
            return False

    @app.route('/')
    def dashboard():
        """Main dashboard."""
        try:
            import asyncio

            # Try to get current status, but handle if services aren't ready yet
            try:
                # Get status from file monitor
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                pending_files = loop.run_until_complete(get_files_by_status('awaiting_review'))
                completed_files = loop.run_until_complete(get_files_by_status('approved'))
                processing_files = loop.run_until_complete(get_files_by_status('processing'))
                failed_files = loop.run_until_complete(get_files_by_status('failed'))

                loop.close()

            except Exception as e:
                logger.error(f"Error getting file statuses: {e}")
                # Fallback to empty data
                pending_files = []
                completed_files = []
                processing_files = []
                failed_files = []

            # Add part mapping info to pending files
            pending_data = []
            for f in pending_files[:10]:
                file_data = {
                    'file_id': f.get('file_id'),
                    'filename': f.get('filename'),
                    'size_mb': f.get('size_mb'),
                    'status': f.get('status'),
                    'created_at': datetime.now().strftime('%Y-%m-%d %H:%M'),  # TODO: Parse from API
                    'preview_url': f'/api/preview/{f.get("file_id")}',
                    'review_url': f'/review/{f.get("file_id")}',
                    'edit_url': f'/edit/{f.get("file_id")}'
                }

                # Add part mapping if available and part_mapper is ready
                if not f.get('part_number') and part_mapper:
                    try:
                        mapping_result = part_mapper.map_filename_to_part_number(f.get('filename', ''))
                        if mapping_result.mapped_part_number:
                            file_data['suggested_part'] = mapping_result.mapped_part_number
                            file_data['mapping_confidence'] = mapping_result.confidence_score
                            file_data['needs_review'] = mapping_result.requires_manual_review
                    except Exception as e:
                        logger.warning(f"Part mapping failed for {f.get('filename')}: {e}")

                pending_data.append(file_data)

            # Enhanced stats
            stats = {
                'pending': len(pending_files),
                'completed': len(completed_files),
                'processing': len(processing_files),
                'failed': len(failed_files)
            }

            completed_data = []
            if completed_files:
                completed_data = [
                    {
                        'file_id': f.get('file_id'),
                        'filename': f.get('filename'),
                        'size_mb': f.get('size_mb'),
                        'completed_at': datetime.now().strftime('%Y-%m-%d %H:%M')  # TODO: Parse from API
                    }
                    for f in completed_files[:10]
                ]

            return render_template('dashboard.html',
                                   pending_files=pending_data,
                                   completed_files=completed_data,
                                   stats=stats,
                                   server_url=f"http://{settings.web.host}:{settings.web.port}",
                                   upload_enabled=True
                                   )
        except Exception as e:
            logger.error(f"Dashboard error: {e}")
            return render_template('error.html', error=str(e)), 500

    @app.route('/upload', methods=['GET', 'POST'])
    async def upload_file():
        """File upload interface."""
        if request.method == 'POST':
            if 'file' not in request.files:
                return jsonify({'success': False, 'error': 'No file selected'}), 400

            file = request.files['file']
            if file.filename == '':
                return jsonify({'success': False, 'error': 'No file selected'}), 400

            if file:
                filename = secure_filename(file.filename)

                # Validate file type
                allowed_extensions = {'.psd', '.png', '.jpg', '.jpeg', '.tiff', '.tif'}
                file_ext = Path(filename).suffix.lower()

                if file_ext not in allowed_extensions:
                    return jsonify({
                        'success': False,
                        'error': f'Unsupported file type: {file_ext}. Allowed: {", ".join(allowed_extensions)}'
                    }), 400

                # Ensure input directory exists
                input_dir = settings.processing.input_dir
                input_dir.mkdir(parents=True, exist_ok=True)

                upload_path = input_dir / filename

                # Handle duplicate filenames
                counter = 1
                original_path = upload_path
                while upload_path.exists():
                    stem = original_path.stem
                    suffix = original_path.suffix
                    upload_path = original_path.parent / f"{stem}_{counter}{suffix}"
                    counter += 1

                try:
                    file.save(upload_path)
                    logger.info(f"File uploaded: {upload_path.name}")

                    # Try to trigger discovery via API
                    try:
                        import asyncio
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)

                        async with httpx.AsyncClient() as client:
                            await client.get(f"{FILE_MONITOR_URL}/scan")

                        loop.close()
                    except Exception as e:
                        logger.warning(f"Failed to trigger file discovery: {e}")

                    return jsonify({
                        'success': True,
                        'message': f'File {upload_path.name} uploaded successfully',
                        'filename': upload_path.name
                    })
                except Exception as e:
                    logger.error(f"Upload failed: {e}")
                    return jsonify({'success': False, 'error': f'Upload failed: {str(e)}'}), 500

        return render_template('upload.html')

    @app.route('/review/<file_id>')
    def review_file(file_id: str):
        """File review interface."""
        import asyncio

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            file_data = loop.run_until_complete(get_file_by_id(file_id))
            loop.close()

            if not file_data:
                return render_template('error.html', error='File not found'), 404

            # Get part mapping if not already done
            part_mapping = None
            if not file_data.get('part_number') and part_mapper:
                try:
                    part_mapping = part_mapper.map_filename_to_part_number(file_data['filename'])
                except Exception as e:
                    logger.warning(f"Part mapping failed: {e}")

            # Get part metadata if we have a part number
            part_metadata = None
            part_number = file_data.get('part_number') or (part_mapping.mapped_part_number if part_mapping else None)
            if part_number and filemaker:
                try:
                    part_metadata = filemaker.get_part_metadata(part_number)
                except Exception as e:
                    logger.warning(f"Failed to get part metadata: {e}")

            return render_template('review.html',
                                   file={
                                       'file_id': file_data['file_id'],
                                       'filename': file_data['filename'],
                                       'status': file_data['status'],
                                       'size_mb': file_data['size_mb'],
                                       'dimensions': None,  # TODO: Add to API
                                       'part_number': part_number,
                                       'part_mapping': part_mapping.dict() if part_mapping else None,
                                       'part_metadata': part_metadata.dict() if part_metadata else None,
                                       'processing_history': file_data.get('processing_history', [])
                                   },
                                   server_url=f"http://{settings.web.host}:{settings.web.port}"
                                   )
        except Exception as e:
            logger.error(f"Review error: {e}")
            return render_template('error.html', error=str(e)), 500

    @app.route('/edit/<file_id>')
    def edit_metadata(file_id: str):
        """Metadata editing interface."""
        import asyncio

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            file_data = loop.run_until_complete(get_file_by_id(file_id))
            loop.close()

            if not file_data:
                return render_template('error.html', error='File not found'), 404

            # Get part mapping if not already done
            part_mapping = None
            if not file_data.get('part_number') and part_mapper:
                try:
                    part_mapping = part_mapper.map_filename_to_part_number(file_data['filename'])
                except Exception as e:
                    logger.warning(f"Part mapping failed: {e}")

            # Get current metadata
            part_number = file_data.get('part_number') or (part_mapping.mapped_part_number if part_mapping else None)
            part_metadata = None
            if part_number and filemaker:
                try:
                    part_metadata = filemaker.get_part_metadata(part_number)
                except Exception as e:
                    logger.warning(f"Failed to get part metadata: {e}")

            return render_template('edit_metadata.html',
                                   file={
                                       'file_id': file_data['file_id'],
                                       'filename': file_data['filename'],
                                       'status': file_data['status'],
                                       'size_mb': file_data['size_mb'],
                                       'part_number': part_number,
                                       'part_mapping': part_mapping.dict() if part_mapping else None,
                                       'metadata_info': part_metadata.dict() if part_metadata else None,
                                       'processing_history': file_data.get('processing_history', [])
                                   },
                                   server_url=f"http://{settings.web.host}:{settings.web.port}"
                                   )
        except Exception as e:
            logger.error(f"Edit metadata error: {e}")
            return render_template('error.html', error=str(e)), 500

    @app.route('/test')
    async def test_route():
        """Simple test route to verify Flask is working."""
        # Test file monitor connection
        file_monitor_status = False
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            async with httpx.AsyncClient() as client:
                response = await client.get(f"{FILE_MONITOR_URL}/health", timeout=5.0)
                file_monitor_status = response.status_code == 200

            loop.close()
        except:
            pass

        return jsonify({
            'status': 'ok',
            'message': 'Flask app is running',
            'timestamp': datetime.now().isoformat(),
            'services': {
                'file_monitor_api': file_monitor_status,
                'part_mapper': part_mapper is not None,
                'filemaker': filemaker is not None,
                'notifier': notifier is not None
            }
        })

    @app.route('/api/status')
    async def api_status():
        """API endpoint for system status."""
        try:
            import asyncio

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            # Get stats from file monitor service
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(f"{FILE_MONITOR_URL}/status")

                    if response.status_code == 200:
                        monitor_data = response.json()
                        total_tracked = monitor_data.get('total_tracked_files', 0)
                    else:
                        total_tracked = 0
            except:
                total_tracked = 0

            # Get file counts by status
            pending_files = loop.run_until_complete(get_files_by_status('awaiting_review'))
            processing_files = loop.run_until_complete(get_files_by_status('processing'))
            completed_files = loop.run_until_complete(get_files_by_status('approved'))
            failed_files = loop.run_until_complete(get_files_by_status('failed'))

            loop.close()

            stats = {
                'pending': len(pending_files),
                'processing': len(processing_files),
                'completed': len(completed_files),
                'failed': len(failed_files),
                'total_tracked': total_tracked,
                'database_connected': filemaker.test_connection() if filemaker else False,
                'part_mapper_ready': len(part_mapper.interchange_cache) > 0 if part_mapper else False,
                'timestamp': datetime.now().isoformat()
            }

            return jsonify(stats)

        except Exception as e:
            logger.error(f"Status API error: {e}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/approve/<file_id>', methods=['POST'])
    def api_approve_file(file_id: str):
        """API endpoint to approve a file for production."""
        try:
            import asyncio

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            success = loop.run_until_complete(update_file_status_api(
                file_id,
                "approved",
                "Approved for production processing"
            ))

            loop.close()

            if success:
                return jsonify({
                    'success': True,
                    'message': 'File approved for production processing'
                })
            else:
                return jsonify({'error': 'File not found or update failed'}), 404

        except Exception as e:
            logger.error(f"Approval API error: {e}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/reject/<file_id>', methods=['POST'])
    def api_reject_file(file_id: str):
        """API endpoint to reject a file."""
        try:
            import asyncio

            data = request.get_json() or {}
            reason = data.get('reason', 'Quality insufficient')

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            success = loop.run_until_complete(update_file_status_api(
                file_id,
                "rejected",
                reason
            ))

            loop.close()

            if success:
                return jsonify({
                    'success': True,
                    'message': 'File rejected'
                })
            else:
                return jsonify({'error': 'File not found or update failed'}), 404

        except Exception as e:
            logger.error(f"Rejection API error: {e}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/preview/<file_id>')
    def api_preview_image(file_id: str):
        """Serve preview image for a file."""
        try:
            import asyncio

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            file_data = loop.run_until_complete(get_file_by_id(file_id))
            loop.close()

            if not file_data:
                return "Image not found", 404

            file_path = Path(file_data['current_location'])
            if not file_path.exists():
                return "Image file not found on disk", 404

            return send_file(file_path)

        except Exception as e:
            logger.error(f"Preview API error: {e}")
            return "Error serving image", 500

    @app.route('/api/part-suggestions')
    def api_part_suggestions():
        """API endpoint for part number suggestions."""
        try:
            query = request.args.get('q', '').strip()
            filename = request.args.get('filename', '')

            if len(query) < 2:
                return jsonify({'suggestions': []})

            if not part_mapper:
                return jsonify({'suggestions': [], 'error': 'Part mapper not available'})

            suggestions = part_mapper.get_manual_override_suggestions(filename, query)

            # Get additional metadata for suggestions
            suggestion_data = []
            for part_number in suggestions[:10]:  # Limit to 10
                metadata = None
                if filemaker:
                    try:
                        metadata = filemaker.get_part_metadata(part_number)
                    except Exception as e:
                        logger.warning(f"Failed to get metadata for {part_number}: {e}")

                suggestion_data.append({
                    'part_number': part_number,
                    'description': metadata.title if metadata else None,
                    'brand': metadata.part_brand if metadata else None,
                    'keywords': metadata.keywords if metadata else None
                })

            return jsonify({'suggestions': suggestion_data})

        except Exception as e:
            logger.error(f"Part suggestions API error: {e}")
            return jsonify({'suggestions': [], 'error': str(e)})

    @app.errorhandler(404)
    def not_found(error):
        return render_template('error.html', error='Page not found'), 404

    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"Internal server error: {error}")
        return render_template('error.html', error='Internal server error'), 500

    @app.errorhandler(Exception)
    def handle_exception(e):
        logger.error(f"Unhandled exception: {e}")
        return render_template('error.html', error=f'Application error: {str(e)}'), 500

    return app


def main():
    """Main entry point for web server."""
    app = create_app()
    app.run(
        host=settings.web.host,
        port=settings.web.port,
        debug=settings.web.debug
    )


if __name__ == '__main__':
    main()