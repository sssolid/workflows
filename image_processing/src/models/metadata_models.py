# ===== src/models/metadata_models.py =====
class PartMetadata(BaseModel):
    """Part metadata from FileMaker database."""
    part_number: str = Field(..., description="Crown part number")
    part_brand: str = Field(default="Crown Automotive")
    title: Optional[str] = None
    description: Optional[str] = None
    keywords: Optional[str] = None
    applications: Optional[str] = None
    category: Optional[str] = None

    class Config:
        extra = "allow"  # Allow additional fields from database


class ExifMetadata(BaseModel):
    """EXIF metadata model."""
    title: Optional[str] = None
    description: Optional[str] = None
    keywords: Optional[str] = None
    author: str = Field(default="Crown Automotive Sales Co., Inc.")
    copyright: str = Field(default="(c) Crown Automotive Sales Co., Inc.")
    software: str = Field(default="Crown Image Processing System")
    camera_make: Optional[str] = None
    camera_model: Optional[str] = None
    datetime_original: Optional[datetime] = None
    dpi: int = Field(default=300, ge=72, le=600)

    # Crown-specific metadata
    part_metadata: Optional[PartMetadata] = None

    class Config:
        extra = "allow"