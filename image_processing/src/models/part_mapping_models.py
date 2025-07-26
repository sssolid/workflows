# ===== src/models/part_mapping_models.py =====
"""
Part Mapping Models - Clean Architecture Implementation
Data models for part number mapping and interchange functionality
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class InterchangeMapping(BaseModel):
    """Model for part number interchange mappings."""
    old_part_number: str = Field(..., description="Original/old part number")
    new_part_number: str = Field(..., description="Current/new part number")
    interchange_code: str = Field(default="", description="Interchange code from database")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Mapping confidence")

    class Config:
        extra = "allow"


class PartMappingResult(BaseModel):
    """Result of part number mapping operation."""
    original_filename: str = Field(..., description="Original image filename")
    extracted_numbers: List[str] = Field(default_factory=list, description="Part numbers extracted from filename")
    mapped_part_number: Optional[str] = Field(None, description="Final mapped part number")
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Confidence in mapping")
    mapping_method: str = Field(default="unknown", description="Method used for mapping")
    interchange_mapping: Optional[InterchangeMapping] = Field(None, description="Interchange mapping used")
    requires_manual_review: bool = Field(default=False, description="Whether manual review is recommended")
    error_message: Optional[str] = Field(None, description="Error message if mapping failed")
    created_at: datetime = Field(default_factory=datetime.now)

    class Config:
        extra = "allow"


class ManualOverride(BaseModel):
    """Model for manual overrides of system determinations."""
    file_id: str = Field(..., description="File identifier")
    override_type: str = Field(..., description="Type of override (part_number, title, description, etc.)")
    system_value: Optional[str] = Field(None, description="Value determined by system")
    user_value: str = Field(..., description="Value provided by user")
    override_reason: Optional[str] = Field(None, description="Reason for override")
    overridden_by: str = Field(..., description="User who made the override")
    overridden_at: datetime = Field(default_factory=datetime.now)

    class Config:
        extra = "allow"


class PartNumberSuggestion(BaseModel):
    """Model for part number suggestions during manual override."""
    part_number: str = Field(..., description="Suggested part number")
    description: Optional[str] = Field(None, description="Part description")
    brand: Optional[str] = Field(None, description="Part brand")
    match_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Match relevance score")
    match_reason: str = Field(default="database_search", description="Why this was suggested")

    class Config:
        extra = "allow"