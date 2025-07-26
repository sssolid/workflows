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
from .part_mapping_models import (
    InterchangeMapping, PartMappingResult, ManualOverride, PartNumberSuggestion
)

__all__ = [
    # File models
    'FileMetadata', 'FileStatus', 'FileType', 'ImageDimensions', 'ProcessedFile',
    # Processing models
    'ProcessingRequest', 'ProcessingResult', 'BackgroundRemovalRequest',
    'FormatGenerationRequest', 'ProcessingModel',
    # Metadata models
    'PartMetadata', 'ExifMetadata',
    # Workflow models
    'WorkflowStep', 'WorkflowInstance',
    # Part mapping models
    'InterchangeMapping', 'PartMappingResult', 'ManualOverride', 'PartNumberSuggestion'
]