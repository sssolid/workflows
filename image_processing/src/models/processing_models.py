# ===== src/models/processing_models.py =====
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path
from pydantic import BaseModel, Field
from enum import Enum


class ProcessingModel(str, Enum):
    """Available processing models."""
    ISNET_GENERAL = "isnet-general-use"
    U2NET = "u2net"
    U2NET_PORTRAIT = "u2net_human_seg"
    SILUETA = "silueta"


class ProcessingRequest(BaseModel):
    """Base request for image processing."""
    file_id: str = Field(..., description="Unique file identifier")
    processing_type: str = Field(..., description="Type of processing requested")
    model: Optional[ProcessingModel] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    priority: int = Field(default=5, ge=1, le=10, description="Processing priority 1-10")
    requested_by: Optional[str] = None
    requested_at: datetime = Field(default_factory=datetime.now)


class ProcessingResult(BaseModel):
    """Result of image processing operation."""
    file_id: str
    processing_type: str
    success: bool
    output_path: Optional[Path] = None
    processing_time_seconds: float
    model_used: Optional[str] = None
    error_message: Optional[str] = None
    quality_score: Optional[float] = Field(None, ge=0, le=100)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)

    class Config:
        # Allow Path objects to be serialized
        arbitrary_types_allowed = True


class BackgroundRemovalRequest(ProcessingRequest):
    """Specific request for background removal."""
    processing_type: str = Field(default="background_removal", const=True)
    model: ProcessingModel = Field(default=ProcessingModel.ISNET_GENERAL)
    enhance_input: bool = Field(default=True)
    post_process: bool = Field(default=True)
    alpha_threshold: int = Field(default=40, ge=0, le=255)


class FormatGenerationRequest(ProcessingRequest):
    """Request for generating multiple output formats."""
    processing_type: str = Field(default="format_generation", const=True)
    output_formats: List[str] = Field(..., min_items=1)
    include_watermark: bool = Field(default=False)
    include_brand_icon: bool = Field(default=False)
    quality_settings: Dict[str, Any] = Field(default_factory=dict)


class BatchProcessingRequest(BaseModel):
    """Request for batch processing multiple files."""
    file_ids: List[str] = Field(..., min_items=1)
    processing_type: str
    common_parameters: Dict[str, Any] = Field(default_factory=dict)
    priority: int = Field(default=5, ge=1, le=10)
    batch_id: Optional[str] = None
    requested_by: Optional[str] = None


class ProcessingProgress(BaseModel):
    """Progress information for long-running operations."""
    file_id: str
    processing_type: str
    status: str  # queued, processing, completed, failed
    progress_percentage: float = Field(ge=0, le=100)
    current_step: Optional[str] = None
    estimated_completion: Optional[datetime] = None
    started_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class QualityMetrics(BaseModel):
    """Quality assessment metrics for processed images."""
    overall_score: float = Field(ge=0, le=100)
    edge_quality: Optional[float] = Field(None, ge=0, le=100)
    color_accuracy: Optional[float] = Field(None, ge=0, le=100)
    artifact_score: Optional[float] = Field(None, ge=0, le=100)
    transparency_quality: Optional[float] = Field(None, ge=0, le=100)
    assessment_method: str = "automated"
    manual_review_required: bool = False
    reviewer_notes: Optional[str] = None


class ProcessingConfiguration(BaseModel):
    """Configuration for processing operations."""
    default_model: ProcessingModel = ProcessingModel.ISNET_GENERAL
    quality_threshold: float = Field(default=70.0, ge=0, le=100)
    auto_approve_threshold: float = Field(default=85.0, ge=0, le=100)
    retry_failed_attempts: int = Field(default=3, ge=0, le=10)
    processing_timeout_seconds: int = Field(default=300, ge=30)
    enable_enhancement: bool = True
    enable_post_processing: bool = True
    notification_settings: Dict[str, Any] = Field(default_factory=dict)


class ProcessingSummary(BaseModel):
    """Summary of processing operations."""
    total_files: int
    successful: int
    failed: int
    pending: int
    average_processing_time: float
    average_quality_score: Optional[float] = None
    period_start: datetime
    period_end: datetime
    top_failure_reasons: List[Dict[str, Any]] = Field(default_factory=list)
    performance_metrics: Dict[str, Any] = Field(default_factory=dict)