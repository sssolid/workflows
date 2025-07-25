# ===== src/__init__.py =====
"""
Crown Automotive Image Processing System
Clean Architecture Implementation

This package provides a modern, scalable image processing system
for Crown Automotive's marketing team.
"""

__version__ = "2.0.0"
__author__ = "Crown Automotive Sales Co., Inc."

# ===== src/models/__init__.py =====
"""Data models for the Crown Automotive Image Processing System."""

from .file_models import (
    FileMetadata, FileStatus, FileType, ImageDimensions, ProcessedFile
)
from .processing_models import (
    ProcessingRequest, ProcessingResult, BackgroundRemovalRequest,
    FormatGenerationRequest, ProcessingModel
)
from .metadata_models import PartMetadata, ExifMetadata
from .workflow_models import WorkflowStep, WorkflowInstance

__all__ = [
    # File models
    'FileMetadata', 'FileStatus', 'FileType', 'ImageDimensions', 'ProcessedFile',
    # Processing models
    'ProcessingRequest', 'ProcessingResult', 'BackgroundRemovalRequest',
    'FormatGenerationRequest', 'ProcessingModel',
    # Metadata models
    'PartMetadata', 'ExifMetadata',
    # Workflow models
    'WorkflowStep', 'WorkflowInstance'
]