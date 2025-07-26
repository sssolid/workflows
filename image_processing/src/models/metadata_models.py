# ===== src/models/metadata_models.py =====
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class PartMetadata(BaseModel):
    """Part metadata from FileMaker database."""
    part_number: str = Field(..., description="Crown part number")
    part_brand: str = Field(default="Crown Automotive")
    title: Optional[str] = None
    description: Optional[str] = None
    keywords: Optional[str] = None
    applications: Optional[str] = None
    category: Optional[str] = None
    # Additional database fields
    sdc_description_short: Optional[str] = None
    sdc_part_description_extended: Optional[str] = None
    sdc_key_search_words: Optional[str] = None
    sdc_slang_description: Optional[str] = None

    class Config:
        extra = "allow"  # Allow additional fields from database


class ExifMetadata(BaseModel):
    """EXIF metadata model for image files."""
    title: Optional[str] = None
    description: Optional[str] = None
    keywords: Optional[str] = None
    author: str = Field(default="Crown Automotive Sales Co., Inc.")
    copyright: str = Field(default="© Crown Automotive Sales Co., Inc.")
    software: str = Field(default="Crown Image Processing System")
    camera_make: Optional[str] = None
    camera_model: Optional[str] = None
    datetime_original: Optional[datetime] = None
    datetime_digitized: Optional[datetime] = None
    dpi: int = Field(default=300, ge=72, le=600)

    # Technical metadata
    color_space: Optional[str] = "sRGB"
    orientation: Optional[int] = 1
    x_resolution: Optional[float] = None
    y_resolution: Optional[float] = None
    resolution_unit: str = "inches"

    # Crown-specific metadata
    part_metadata: Optional[PartMetadata] = None
    processing_software: str = "Crown Image Processing System v2.0"
    processing_date: datetime = Field(default_factory=datetime.now)
    quality_score: Optional[float] = Field(None, ge=0, le=100)

    class Config:
        extra = "allow"


class ImageMetadata(BaseModel):
    """Complete image metadata including technical and business information."""
    # File information
    filename: str
    file_size_bytes: int
    file_format: str

    # Image properties
    width: int
    height: int
    bit_depth: Optional[int] = None
    color_mode: Optional[str] = None
    has_transparency: bool = False

    # EXIF data
    exif_data: Optional[ExifMetadata] = None

    # Part information
    part_metadata: Optional[PartMetadata] = None

    # Processing metadata
    original_filename: Optional[str] = None
    processing_history: List[Dict[str, Any]] = Field(default_factory=list)
    quality_metrics: Dict[str, Any] = Field(default_factory=dict)

    # Business metadata
    approved_by: Optional[str] = None
    approval_date: Optional[datetime] = None
    usage_rights: str = Field(default="Internal Crown Automotive use only")

    class Config:
        extra = "allow"


class MetadataTemplate(BaseModel):
    """Template for standardized metadata application."""
    template_name: str
    template_version: str = "1.0"
    description: Optional[str] = None

    # Default values
    default_author: str = "Crown Automotive Sales Co., Inc."
    default_copyright: str = "© Crown Automotive Sales Co., Inc."
    default_software: str = "Crown Image Processing System"
    default_keywords: List[str] = Field(default_factory=list)

    # Field mappings from part metadata
    title_mapping: str = "title"  # Field to use for title
    description_mapping: str = "description"  # Field to use for description
    keywords_mapping: List[str] = Field(default=["keywords", "sdc_key_search_words"])

    # Processing settings
    include_processing_date: bool = True
    include_quality_score: bool = True
    include_part_number: bool = True

    # Validation rules
    required_fields: List[str] = Field(default_factory=list)
    max_keyword_length: int = 255
    max_description_length: int = 1000

    class Config:
        extra = "allow"


class MetadataValidationResult(BaseModel):
    """Result of metadata validation."""
    is_valid: bool
    validation_errors: List[str] = Field(default_factory=list)
    validation_warnings: List[str] = Field(default_factory=list)
    missing_required_fields: List[str] = Field(default_factory=list)
    field_length_violations: List[Dict[str, Any]] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)

    class Config:
        extra = "allow"


class MetadataExportFormat(BaseModel):
    """Configuration for metadata export formats."""
    format_name: str  # "exif", "xmp", "iptc", "csv", "json"
    include_fields: List[str] = Field(default_factory=list)  # Empty = all fields
    exclude_fields: List[str] = Field(default_factory=list)
    field_mappings: Dict[str, str] = Field(default_factory=dict)  # Custom field names
    date_format: str = "%Y-%m-%d %H:%M:%S"
    encoding: str = "utf-8"

    class Config:
        extra = "allow"