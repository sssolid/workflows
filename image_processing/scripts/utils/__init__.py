"""
Crown Automotive Image Processing Utilities
Shared utility modules for image processing workflow
"""

__version__ = "1.0.0"
__author__ = "Crown Automotive Sales Co., Inc."

# Import main utility classes
from .filemaker_conn import FileMakerConnection, get_filemaker_connection
from .image_utils import (
    ImageInfo,
    validate_image_file,
    crop_to_content,
    enhance_for_background_removal,
    create_thumbnail,
    compare_images,
    extract_dominant_colors,
    get_image_quality_score
)

__all__ = [
    'FileMakerConnection',
    'get_filemaker_connection',
    'ImageInfo',
    'validate_image_file',
    'crop_to_content',
    'enhance_for_background_removal',
    'create_thumbnail',
    'compare_images',
    'extract_dominant_colors',
    'get_image_quality_score'
]