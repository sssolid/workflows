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

from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, flash
from werkzeug.utils import secure_filename

from ..config.settings import settings
from ..services.file_monitor_service import FileMonitorService
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


def create_app() -> Flask:
    """Create and configure Flask application."""
    app = Flask(__name__, template_folder='/app/templates')
    app.config['SECRET_KEY'] = settings.web.secret_key
    app.config['MAX_CONTENT_LENGTH'] = settings.processing.max_file_size_bytes

    # Initialize services (gracefully handle failures)
    file_monitor = None
    part_mapper = None
    filemaker = None
    notifier = None

    try:
        file_monitor = FileMonitorService()
        logger.info("File monitor service initialized")
    except Exception as e:
        logger.warning(f"File monitor service failed to initialize: {e}")

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

    @app.route('/')
    def dashboard():
        """Main dashboard."""
        try:
            # Try to get current status, but handle if services aren't ready yet
            if not file_monitor:
                return render_template('dashboard.html',
                                       pending_files=[],
                                       completed_files=[],
                                       stats={'pending': 0, 'completed': 0, 'processing': 0, 'failed': 0},
                                       server_url=f"http://{settings.web.host}:{settings.web.port}",
                                       upload_enabled=True
                                       )

            # Get current status
            pending_files = file_monitor.get_files_by_status(FileStatus.AWAITING_REVIEW)
            completed_files = file_monitor.get_files_by_status(FileStatus.APPROVED)
            processing_files = file_monitor.get_files_by_status(FileStatus.PROCESSING)
            failed_files = file_monitor.get_files_by_status(FileStatus.FAILED)

            # Add part mapping info to pending files
            pending_data = []
            for f in pending_files[:10]:
                file_data = {
                    'file_id': f.metadata.file_id,
                    'filename': f.metadata.filename,
                    'size_mb': f.metadata.size_mb,
                    'status': f.metadata.status.value,
                    'created_at': f.metadata.created_at.strftime('%Y-%m-%d %H:%M'),
                    'preview_url': f'/api/preview/{f.metadata.file_id}',
                    'review_url': f'/review/{f.metadata.file_id}',
                    'edit_url': f'/edit/{f.metadata.file_id}'
                }

                # Add part mapping if available
                if not f.part_number and part_mapper:
                    try:
                        mapping_result = part_mapper.map_filename_to_part_number(f.metadata.filename)
                        if mapping_result.mapped_part_number:
                            file_data['suggested_part'] = mapping_result.mapped_part_number
                            file_data['mapping_confidence'] = mapping_result.confidence_score
                            file_data['needs_review'] = mapping_result.requires_manual_review
                    except Exception as e:
                        logger.warning(f"Part mapping failed for {f.metadata.filename}: {e}")

                pending_data.append(file_data)

            # Enhanced stats
            stats = {
                'pending': len(pending_files) if pending_files else 0,
                'completed': len(completed_files) if completed_files else 0,
                'processing': len(processing_files) if processing_files else 0,
                'failed': len(failed_files) if failed_files else 0
            }

            completed_data = []
            if completed_files:
                completed_data = [
                    {
                        'file_id': f.metadata.file_id,
                        'filename': f.metadata.filename,
                        'size_mb': f.metadata.size_mb,
                        'completed_at': f.metadata.created_at.strftime('%Y-%m-%d %H:%M')
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
    def upload_file():
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

                    # Try to trigger discovery if file monitor is available
                    if file_monitor:
                        try:
                            # Give the file a moment to be fully written
                            import time
                            time.sleep(0.5)
                            file_monitor.discover_new_files()
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
        if not file_monitor:
            return render_template('error.html', error='File monitor service not available'), 503

        file_obj = file_monitor.get_file_by_id(file_id)
        if not file_obj:
            return render_template('error.html', error='File not found'), 404

        # Get part mapping if not already done
        part_mapping = None
        if not file_obj.part_number and part_mapper:
            try:
                part_mapping = part_mapper.map_filename_to_part_number(file_obj.metadata.filename)
            except Exception as e:
                logger.warning(f"Part mapping failed: {e}")

        # Get part metadata if we have a part number
        part_metadata = None
        part_number = file_obj.part_number or (part_mapping.mapped_part_number if part_mapping else None)
        if part_number and filemaker:
            try:
                part_metadata = filemaker.get_part_metadata(part_number)
            except Exception as e:
                logger.warning(f"Failed to get part metadata: {e}")

        return render_template('review.html',
                               file={
                                   'file_id': file_obj.metadata.file_id,
                                   'filename': file_obj.metadata.filename,
                                   'status': file_obj.metadata.status.value,
                                   'size_mb': file_obj.metadata.size_mb,
                                   'dimensions': file_obj.dimensions.dict() if file_obj.dimensions else None,
                                   'part_number': part_number,
                                   'part_mapping': part_mapping.dict() if part_mapping else None,
                                   'part_metadata': part_metadata.dict() if part_metadata else None,
                                   'processing_history': file_obj.processing_history
                               },
                               server_url=f"http://{settings.web.host}:{settings.web.port}"
                               )

    @app.route('/edit/<file_id>')
    def edit_metadata(file_id: str):
        """Metadata editing interface."""
        if not file_monitor:
            return render_template('error.html', error='File monitor service not available'), 503

        file_obj = file_monitor.get_file_by_id(file_id)
        if not file_obj:
            return render_template('error.html', error='File not found'), 404

        # Get part mapping if not already done
        part_mapping = None
        if not file_obj.part_number and part_mapper:
            try:
                part_mapping = part_mapper.map_filename_to_part_number(file_obj.metadata.filename)
            except Exception as e:
                logger.warning(f"Part mapping failed: {e}")

        # Get current metadata
        part_number = file_obj.part_number or (part_mapping.mapped_part_number if part_mapping else None)
        part_metadata = None
        if part_number and filemaker:
            try:
                part_metadata = filemaker.get_part_metadata(part_number)
            except Exception as e:
                logger.warning(f"Failed to get part metadata: {e}")

        return render_template('edit_metadata.html',
                               file={
                                   'file_id': file_obj.metadata.file_id,
                                   'filename': file_obj.metadata.filename,
                                   'status': file_obj.metadata.status.value,
                                   'size_mb': file_obj.metadata.size_mb,
                                   'part_number': part_number,
                                   'part_mapping': part_mapping.dict() if part_mapping else None,
                                   'metadata_info': part_metadata.dict() if part_metadata else None,
                                   'processing_history': file_obj.processing_history
                               },
                               server_url=f"http://{settings.web.host}:{settings.web.port}"
                               )

    @app.route('/test')
    def test_route():
        """Simple test route to verify Flask is working."""
        return jsonify({
            'status': 'ok',
            'message': 'Flask app is running',
            'timestamp': datetime.now().isoformat(),
            'services': {
                'file_monitor': file_monitor is not None,
                'part_mapper': part_mapper is not None,
                'filemaker': filemaker is not None,
                'notifier': notifier is not None
            }
        })

    @app.route('/api/status')
    def api_status():
        """API endpoint for system status."""
        try:
            if not file_monitor:
                return jsonify({
                    'error': 'File monitor not available',
                    'timestamp': datetime.now().isoformat()
                }), 503

            stats = {
                'pending': len(file_monitor.get_files_by_status(FileStatus.AWAITING_REVIEW)),
                'processing': len(file_monitor.get_files_by_status(FileStatus.PROCESSING)),
                'completed': len(file_monitor.get_files_by_status(FileStatus.APPROVED)),
                'failed': len(file_monitor.get_files_by_status(FileStatus.FAILED)),
                'total_tracked': len(file_monitor._tracked_files),
                'database_connected': filemaker.test_connection() if filemaker else False,
                'part_mapper_ready': len(part_mapper.interchange_cache) > 0 if part_mapper else False,
                'timestamp': datetime.now().isoformat()
            }

            return jsonify(stats)

        except Exception as e:
            logger.error(f"Status API error: {e}")
            return jsonify({'error': str(e)}), 500

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

    @app.route('/api/update-metadata', methods=['POST'])
    def api_update_metadata():
        """API endpoint to update file metadata with manual overrides."""
        try:
            if not file_monitor:
                return jsonify({'error': 'File monitor service not available'}), 503

            data = request.get_json()
            file_id = data.get('file_id')

            if not file_id:
                return jsonify({'error': 'File ID required'}), 400

            file_obj = file_monitor.get_file_by_id(file_id)
            if not file_obj:
                return jsonify({'error': 'File not found'}), 404

            # Validate part number if provided
            part_number = data.get('part_number', '').strip()
            if part_number and part_mapper and not part_mapper.validate_part_number(part_number):
                return jsonify({'error': f'Part number {part_number} not found in database'}), 400

            # Create manual overrides for changed values
            overrides = []
            current_user = "web_user"  # TODO: Get from session/auth

            # Check part number override
            if part_number and part_number != file_obj.part_number:
                overrides.append(ManualOverride(
                    file_id=file_id,
                    override_type="part_number",
                    system_value=file_obj.part_number,
                    user_value=part_number,
                    override_reason=data.get('override_reason'),
                    overridden_by=current_user
                ))
                file_obj.part_number = part_number

            # Store overrides in file history
            for override in overrides:
                file_obj.add_processing_step("manual_override", override.dict())

            # Update file metadata
            file_obj.add_processing_step("metadata_updated", {
                "updated_fields": list(data.keys()),
                "user": current_user,
                "reason": data.get('override_reason')
            })

            # If approve_after_save is true, approve the file
            if data.get('approve_after_save'):
                file_monitor.update_file_status(
                    file_id,
                    FileStatus.APPROVED,
                    "Manually reviewed and approved"
                )

                # Trigger format generation
                logger.info(f"File {file_id} approved after manual review")

            return jsonify({
                'success': True,
                'message': 'Metadata updated successfully',
                'approved': data.get('approve_after_save', False)
            })

        except Exception as e:
            logger.error(f"Update metadata API error: {e}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/approve/<file_id>', methods=['POST'])
    def api_approve_file(file_id: str):
        """API endpoint to approve a file for production."""
        try:
            if not file_monitor:
                return jsonify({'error': 'File monitor service not available'}), 503

            success = file_monitor.update_file_status(
                file_id,
                FileStatus.APPROVED,
                "Approved for production processing"
            )

            if success:
                return jsonify({
                    'success': True,
                    'message': 'File approved for production processing'
                })
            else:
                return jsonify({'error': 'File not found'}), 404

        except Exception as e:
            logger.error(f"Approval API error: {e}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/reject/<file_id>', methods=['POST'])
    def api_reject_file(file_id: str):
        """API endpoint to reject a file."""
        try:
            if not file_monitor:
                return jsonify({'error': 'File monitor service not available'}), 503

            data = request.get_json() or {}
            reason = data.get('reason', 'Quality insufficient')

            success = file_monitor.update_file_status(
                file_id,
                FileStatus.REJECTED,
                reason
            )

            if success:
                return jsonify({
                    'success': True,
                    'message': 'File rejected'
                })
            else:
                return jsonify({'error': 'File not found'}), 404

        except Exception as e:
            logger.error(f"Rejection API error: {e}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/preview/<file_id>')
    def api_preview_image(file_id: str):
        """Serve preview image for a file."""
        try:
            if not file_monitor:
                return "File monitor not available", 503

            file_obj = file_monitor.get_file_by_id(file_id)
            if not file_obj or not file_obj.current_location:
                return "Image not found", 404

            if not file_obj.current_location.exists():
                return "Image file not found on disk", 404

            return send_file(file_obj.current_location)

        except Exception as e:
            logger.error(f"Preview API error: {e}")
            return "Error serving image", 500

    @app.route('/api/decisions/pending')
    def api_pending_decisions():
        """API endpoint for checking pending decisions (for n8n)."""
        try:
            if not file_monitor:
                return jsonify({'decisions': [], 'count': 0, 'error': 'File monitor not available'})

            # Check for files that were just approved/rejected
            decisions = []

            # Get recently approved files
            approved_files = file_monitor.get_files_by_status(FileStatus.APPROVED)
            for file_obj in approved_files:
                # Check if this is a recent approval
                if file_obj.processing_history:
                    last_step = file_obj.processing_history[-1]
                    if last_step.get('step') == 'status_change' and \
                            last_step.get('details', {}).get('to') == FileStatus.APPROVED.value:
                        decisions.append({
                            'file_id': file_obj.metadata.file_id,
                            'action': 'approve',
                            'decision_id': f"approve_{file_obj.metadata.file_id}",
                            'timestamp': last_step.get('timestamp')
                        })

            return jsonify({
                'decisions': decisions,
                'count': len(decisions)
            })

        except Exception as e:
            logger.error(f"Pending decisions API error: {e}")
            return jsonify({'decisions': [], 'count': 0, 'error': str(e)})

    @app.route('/browse/production/')
    def browse_production():
        """Browse production files."""
        try:
            production_dir = settings.processing.production_dir
            if not production_dir.exists():
                return render_template('error.html', error='Production directory not found'), 404

            # This would list production files - implementation depends on requirements
            return jsonify({
                'message': 'Production file browsing not yet implemented',
                'production_dir': str(production_dir)
            })

        except Exception as e:
            logger.error(f"Browse production error: {e}")
            return render_template('error.html', error=str(e)), 500

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