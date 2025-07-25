# ===== src/models/file_models.py =====
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, validator
import hashlib


class FileStatus(str, Enum):
    """File processing status enumeration."""
    DISCOVERED = "discovered"
    QUEUED = "queued"
    PROCESSING = "processing"
    PROCESSED = "processed"
    AWAITING_REVIEW = "awaiting_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    FAILED = "failed"


class FileType(str, Enum):
    """Supported file types."""
    PSD = "psd"
    PNG = "png"
    JPEG = "jpeg"
    TIFF = "tiff"
    BMP = "bmp"


class FileMetadata(BaseModel):
    """Core file metadata model."""
    file_id: str = Field(..., description="Unique file identifier based on path + checksum")
    original_path: Path = Field(..., description="Original file path")
    filename: str = Field(..., description="Original filename")
    file_type: FileType = Field(..., description="Detected file type")
    size_bytes: int = Field(..., description="File size in bytes")
    checksum_md5: str = Field(..., description="MD5 checksum for duplicate detection")
    checksum_sha256: str = Field(..., description="SHA256 checksum for integrity")
    created_at: datetime = Field(default_factory=datetime.now)
    modified_at: datetime = Field(..., description="File modification time")
    status: FileStatus = Field(default=FileStatus.DISCOVERED)

    @validator('file_id')
    def validate_file_id(cls, v):
        if not v or len(v) < 10:
            raise ValueError('file_id must be at least 10 characters')
        return v

    @property
    def size_mb(self) -> float:
        """File size in megabytes."""
        return round(self.size_bytes / (1024 * 1024), 2)

    @property
    def stem(self) -> str:
        """Filename without extension."""
        return Path(self.filename).stem

    @property
    def is_psd(self) -> bool:
        """Check if file is a PSD."""
        return self.file_type == FileType.PSD


class ImageDimensions(BaseModel):
    """Image dimensions model."""
    width: int = Field(..., gt=0)
    height: int = Field(..., gt=0)

    @property
    def aspect_ratio(self) -> float:
        """Calculate aspect ratio."""
        return self.width / self.height

    @property
    def megapixels(self) -> float:
        """Calculate megapixels."""
        return round((self.width * self.height) / 1_000_000, 2)

    @property
    def is_high_resolution(self) -> bool:
        """Check if image is high resolution (>= 2500px on longest side)."""
        return max(self.width, self.height) >= 2500


class ProcessedFile(BaseModel):
    """Model for files that have been processed."""
    metadata: FileMetadata
    dimensions: Optional[ImageDimensions] = None
    processing_history: List[Dict[str, Any]] = Field(default_factory=list)
    current_location: Optional[Path] = None
    backup_locations: List[Path] = Field(default_factory=list)
    part_number: Optional[str] = None

    def add_processing_step(self, step_name: str, details: Dict[str, Any]) -> None:
        """Add a processing step to history."""
        self.processing_history.append({
            "step": step_name,
            "timestamp": datetime.now().isoformat(),
            "details": details
        })

    def update_status(self, new_status: FileStatus, reason: Optional[str] = None) -> None:
        """Update file status with optional reason."""
        old_status = self.metadata.status
        self.metadata.status = new_status

        self.add_processing_step("status_change", {
            "from": old_status,
            "to": new_status,
            "reason": reason
        })