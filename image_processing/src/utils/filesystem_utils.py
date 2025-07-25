# ===== src/utils/filesystem_utils.py =====
import time
from pathlib import Path
from typing import List, Optional
from ..models.file_models import FileType


def is_file_stable(file_path: Path, wait_seconds: int = 2) -> bool:
    """
    Check if a file is stable (not being written to).

    Args:
        file_path: Path to check
        wait_seconds: Seconds to wait before checking again

    Returns:
        True if file is stable
    """
    try:
        initial_size = file_path.stat().st_size
        time.sleep(wait_seconds)
        return file_path.stat().st_size == initial_size
    except (OSError, FileNotFoundError):
        return False


def detect_file_type(file_path: Path) -> Optional[FileType]:
    """
    Detect file type from extension.

    Args:
        file_path: Path to analyze

    Returns:
        Detected FileType or None
    """
    extension = file_path.suffix.lower()

    type_mapping = {
        '.psd': FileType.PSD,
        '.png': FileType.PNG,
        '.jpg': FileType.JPEG,
        '.jpeg': FileType.JPEG,
        '.tif': FileType.TIFF,
        '.tiff': FileType.TIFF,
        '.bmp': FileType.BMP,
    }

    return type_mapping.get(extension)


def is_valid_image_file(file_path: Path, min_size_bytes: int = 1024) -> bool:
    """
    Validate if file is a processable image.

    Args:
        file_path: Path to validate
        min_size_bytes: Minimum file size

    Returns:
        True if valid
    """
    if not file_path.is_file():
        return False

    # Check if it's a supported type
    if not detect_file_type(file_path):
        return False

    # Skip processed files to prevent loops
    if '_bg_removed' in file_path.name or file_path.name.startswith('.'):
        return False

    # Check file size
    try:
        if file_path.stat().st_size < min_size_bytes:
            return False
    except OSError:
        return False

    # Check if file is stable
    return is_file_stable(file_path)


def ensure_directory(path: Path) -> None:
    """Ensure directory exists, create if it doesn't."""
    path.mkdir(parents=True, exist_ok=True)