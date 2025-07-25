# ===== src/models/processing_models.py =====
from typing import Dict, List, Optional, Union
from pydantic import BaseModel, Field
from enum import Enum


class ProcessingModel(str, Enum):
    """Available processing models."""
    ISNET_GENERAL = "isnet-general-use"
    U2NET = "u2net"
    U2NET_PORTRAIT = "u2net_human_seg"
    SILUETA = "silueta"


class ProcessingRequest(BaseModel):
    """Request for image processing."""
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