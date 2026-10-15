"""
CompressPro AI - Core Domain Models and State Machine Definitions
Adheres to Master Architecture Blueprint Section 8, 9, 10, and 21.
"""

from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from pydantic import BaseModel, Field


class JobState(str, Enum):
    CREATED = "created"
    VALIDATING = "validating"
    QUEUED = "queued"
    RUNNING = "running"
    FINALIZING = "finalizing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class JobOperation(str, Enum):
    # Image Operations
    IMAGE_COMPRESS = "image.compress"
    IMAGE_RESIZE = "image.resize"
    IMAGE_CONVERT = "image.convert"
    IMAGE_CROP = "image.crop"
    IMAGE_ROTATE = "image.rotate"
    IMAGE_METADATA = "image.metadata"
    IMAGE_TO_PDF = "image.to_pdf"

    # PDF Operations
    PDF_COMPRESS = "pdf.compress"
    PDF_MERGE = "pdf.merge"
    PDF_SPLIT = "pdf.split"
    PDF_ROTATE = "pdf.rotate"
    PDF_REORDER = "pdf.reorder"
    PDF_EXTRACT = "pdf.extract"
    PDF_TO_IMAGES = "pdf.to_images"

    # Video Operations
    VIDEO_COMPRESS = "video.compress"
    VIDEO_CONVERT = "video.convert"
    VIDEO_TRIM = "video.trim"
    VIDEO_RESIZE = "video.resize"
    VIDEO_AUDIO = "video.audio"
    VIDEO_PROBE = "video.probe"


class ErrorCode(str, Enum):
    UNSUPPORTED_MEDIA_TYPE = "UNSUPPORTED_MEDIA_TYPE"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    MEDIA_LIMIT_EXCEEDED = "MEDIA_LIMIT_EXCEEDED"
    CORRUPT_INPUT = "CORRUPT_INPUT"
    PASSWORD_REQUIRED = "PASSWORD_REQUIRED"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    PROCESSOR_TIMEOUT = "PROCESSOR_TIMEOUT"
    WORKER_UNAVAILABLE = "WORKER_UNAVAILABLE"
    STORAGE_TEMPORARY_ERROR = "STORAGE_TEMPORARY_ERROR"
    OUTPUT_VALIDATION_FAILED = "OUTPUT_VALIDATION_FAILED"
    CANCELLED_BY_USER = "CANCELLED_BY_USER"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class JobProgress(BaseModel):
    stage: str = Field(..., description="Current processing stage (e.g. validating, encoding, verifying)")
    percent: int = Field(default=0, ge=0, le=100, description="Estimated completion percentage")
    message: Optional[str] = Field(default=None, description="Human-readable progress description")


class JobError(BaseModel):
    code: ErrorCode
    message: str
    request_id: Optional[str] = None
    retryable: bool = False
    details: Optional[Dict[str, Any]] = None


class ArtifactMetadata(BaseModel):
    id: str
    job_id: str
    object_key: str
    filename: str
    mime: str
    bytes: int
    checksum_sha256: str
    width: Optional[int] = None
    height: Optional[int] = None
    duration_seconds: Optional[float] = None
    page_count: Optional[int] = None
    compression_ratio: Optional[float] = None
    savings_percent: Optional[float] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None


class JobRecord(BaseModel):
    id: str
    owner_id: str = "guest_default"
    operation: JobOperation
    state: JobState = JobState.CREATED
    input_file_ids: List[str]
    settings: Dict[str, Any] = Field(default_factory=dict)
    progress: JobProgress = Field(default_factory=lambda: JobProgress(stage="created", percent=0))
    error: Optional[JobError] = None
    retryable: bool = False
    attempt: int = 1
    max_attempts: int = 3
    idempotency_key: Optional[str] = None
    artifacts: List[ArtifactMetadata] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
