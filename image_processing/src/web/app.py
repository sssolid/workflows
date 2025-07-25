# ===== src/web/app.py =====
"""
Web Application - Clean Architecture Implementation
Flask application with clean separation of concerns
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
from werkzeug.utils import secure_filename

from ..config.settings import settings
from ..services.file_monitor_service import FileMonitorService
from ..services.background_removal_service import BackgroundRemovalService
from ..services.image_processing_service import ImageProcessingService
from ..services.filemaker_service import FileMakerService
from ..services.notification_service import NotificationService
from ..models.file_models import FileStatus
from ..models.processing_models import BackgroundRemovalRequest, FormatGenerationRequest, ProcessingModel
from ..utils.logging_config import setup_logging

# Setup logging
setup_logging(settings.log_level)
logger = logging.getLogger(__name__)


def create_app() -> Flask:
    """Create and configure Flask application."""
    app = Flask(__name__)
    app.config['SECRET_KEY'] = settings.web.secret_key
    app.config['MAX_CONTENT_LENGTH'] = settings.processing.max_file_size_bytes

    # Initialize services
    file_monitor = FileMonitorService()
    filemaker = FileMakerService()
    notifier = NotificationService()

    @app.route('/')
    def dashboard():
        """Main dashboard."""
        try:
            # Get current status
            pending_files = file_monitor.get_files_by_status(FileStatus.AWAITING_REVIEW)
            completed_files = file_monitor.get_files_by_status(FileStatus.APPROVED)

            return render_template('dashboard.html', {
                'pending_files': [
                    {
                        'file_id': f.metadata.file_id,
                        'filename': f.metadata.filename,
                        'size_mb': f.metadata.size_mb,
                        'status': f.metadata.status,
                        'created_at': f.metadata.created_at.isoformat(),
                        'preview_url': f'/preview/{f.metadata.file_id}',
                        'review_url': f'/review/{f.metadata.file_id}'
                    }
                    for f in pending_files[:10]
                ],
                'completed_files': [
                    {
                        'file_id': f.metadata.file_id,
                        'filename': f.metadata.filename,
                        'size_mb': f.metadata.size_mb,
                        'completed_at': f.metadata.created_at.isoformat()
                    }
                    for f in completed_files[:10]
                ],
                'stats': {
                    'pending': len(pending_files),
                    'completed': len(completed_files),
                    'processing': len(file_monitor.get_files_by_status(FileStatus.PROCESSING)),
                    'failed': len(file_monitor.get_files_by_status(FileStatus.FAILED))
                },
                'server_url': f"http://{settings.web.host}:{settings.web.port}"
            })
        except Exception as e:
            logger.error(f"Dashboard error: {e}")
            return render_template('error.html', error=str(e)), 500

    @app.route('/upload', methods=['GET', 'POST'])
    def upload_file():
        """File upload interface."""
        if request.method == 'POST':
            if 'file' not in request.files:
                return jsonify({'error': 'No file selected'}), 400

            file = request.files['file']
            if file.filename == '':
                return jsonify({'error': 'No file selected'}), 400

            if file:
                filename = secure_filename(file.filename)
                upload_path = settings.processing.input_dir / filename

                try:
                    file.save(upload_path)
                    logger.info(f"File uploaded: {filename}")
                    return jsonify({
                        'success': True,
                        'message': f'File {filename} uploaded successfully',
                        'filename': filename
                    })
                except Exception as e:
                    logger.error(f"Upload failed: {e}")
                    return jsonify({'error': f'Upload failed: {str(e)}'}), 500

        return render_template('upload.html')

    @app.route('/review/<file_id>')
    def review_file(file_id: str):
        """File review interface."""
        file_obj = file_monitor.get_file_by_id(file_id)
        if not file_obj:
            return render_template('error.html', error='File not found'), 404

        # Get part metadata if available
        part_metadata = None
        if file_obj.part_number:
            part_metadata = filemaker.get_part_metadata(file_obj.part_number)

        return render_template('review.html', {
            'file': {
                'file_id': file_obj.metadata.file_id,
                'filename': file_obj.metadata.filename,
                'status': file_obj.metadata.status,
                'size_mb': f.metadata.size_mb,
                'dimensions': file_obj.dimensions.dict() if file_obj.dimensions else None,
                'part_metadata': part_metadata.dict() if part_metadata else None,
                'processing_history': file_obj.processing_history
            },
            'server_url': f"http://{settings.web.host}:{settings.web.port}"
        })

    @app.route('/api/status')
    def api_status():
        """API endpoint for system status."""
        try:
            stats = {
                'pending': len(file_monitor.get_files_by_status(FileStatus.AWAITING_REVIEW)),
                'processing': len(file_monitor.get_files_by_status(FileStatus.PROCESSING)),
                'completed': len(file_monitor.get_files_by_status(FileStatus.APPROVED)),
                'failed': len(file_monitor.get_files_by_status(FileStatus.FAILED)),
                'total_tracked': len(file_monitor._tracked_files),
                'database_connected': filemaker.test_connection(),
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
            # This will be handled by the image processor service
            # Just update status here and let the workflow handle processing
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

    @app.route('/api/decisions/pending')
    def api_pending_decisions():
        """API endpoint for checking pending decisions (for n8n)."""
        try:
            # Check for files that were just approved/rejected
            decisions = []

            # Get recently approved files
            approved_files = file_monitor.get_files_by_status(FileStatus.APPROVED)
            for file_obj in approved_files:
                # Check if this is a recent approval
                if file_obj.processing_history:
                    last_step = file_obj.processing_history[-1]
                    if last_step.get('step') == 'status_change' and \
                            last_step.get('details', {}).get('to') == FileStatus.APPROVED:
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

    @app.errorhandler(404)
    def not_found(error):
        return render_template('error.html', error='Page not found'), 404

    @app.errorhandler(500)
    def internal_error(error):
        return render_template('error.html', error='Internal server error'), 500

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
