# ===== src/utils/__init__.py =====
"""Utility modules for the Crown Automotive Image Processing System."""

from .crypto_utils import calculate_file_checksums, generate_file_id
from .filesystem_utils import (
    is_file_stable, detect_file_type, is_valid_image_file, ensure_directory
)
from .error_handling import (
    ProcessingError, FileNotFoundError, InvalidFileError,
    ProcessingTimeoutError, handle_processing_errors
)
from .logging_config import setup_logging

__all__ = [
    # Crypto utilities
    'calculate_file_checksums', 'generate_file_id',
    # Filesystem utilities
    'is_file_stable', 'detect_file_type', 'is_valid_image_file', 'ensure_directory',
    # Error handling
    'ProcessingError', 'FileNotFoundError', 'InvalidFileError',
    'ProcessingTimeoutError', 'handle_processing_errors',
    # Logging
    'setup_logging'
]