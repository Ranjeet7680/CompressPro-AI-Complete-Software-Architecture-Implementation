"""
CompressPro AI - Real Relational Database Models (SQLAlchemy)
Adheres directly to Master Architecture Blueprint Section 9 (Core Domain Model & Database).
Supported Engines: SQLite (default local) & PostgreSQL (production via DATABASE_URL).
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Text, ForeignKey, Index, UniqueConstraint
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def generate_uuid() -> str:
    return uuid.uuid4().hex


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=True, index=True)
    role = Column(String(50), default="guest", nullable=False)  # guest, free, pro, admin
    status = Column(String(50), default="active", nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    files = relationship("FileAsset", back_populates="owner", cascade="all, delete-orphan")
    jobs = relationship("Job", back_populates="owner", cascade="all, delete-orphan")


class FileAsset(Base):
    """
    Metadata for source uploaded media files.
    Object keys reference sandboxed private object storage.
    """
    __tablename__ = "file_assets"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    owner_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    object_key = Column(String(512), unique=True, nullable=False, index=True)
    original_filename = Column(String(512), nullable=False)
    detected_mime = Column(String(100), nullable=False)
    bytes = Column(Integer, nullable=False)
    checksum_sha256 = Column(String(64), nullable=False, index=True)
    status = Column(String(50), default="validated", nullable=False)  # quarantine, validated, expired
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=True, index=True)

    owner = relationship("User", back_populates="files")
    job_inputs = relationship("JobInput", back_populates="file_asset", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_file_assets_owner_created", "owner_id", "created_at"),
    )


class Job(Base):
    """
    State machine records for media processing tasks.
    """
    __tablename__ = "jobs"

    id = Column(String(36), primary_key=True, default=lambda: f"job_{generate_uuid()[:12]}")
    owner_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    operation = Column(String(100), nullable=False, index=True)
    state = Column(String(50), default="created", nullable=False, index=True)  # created, validating, queued, running, finalizing, succeeded, failed, cancelled, rejected, expired
    
    # Configuration and Progress
    settings_json = Column(Text, default="{}", nullable=False)
    progress_stage = Column(String(100), default="created", nullable=False)
    progress_percent = Column(Integer, default=0, nullable=False)
    progress_message = Column(Text, nullable=True)

    # Retries and Idempotency
    attempt = Column(Integer, default=1, nullable=False)
    max_attempts = Column(Integer, default=3, nullable=False)
    idempotency_key = Column(String(255), nullable=True, index=True)

    # Errors
    error_code = Column(String(100), nullable=True)
    error_message = Column(Text, nullable=True)
    error_details_json = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    owner = relationship("User", back_populates="jobs")
    inputs = relationship("JobInput", back_populates="job", cascade="all, delete-orphan", order_by="JobInput.ordinal")
    artifacts = relationship("Artifact", back_populates="job", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_jobs_owner_created", "owner_id", "created_at"),
        Index("idx_jobs_state_created", "state", "created_at"),
        UniqueConstraint("owner_id", "idempotency_key", name="uq_owner_idempotency"),
    )


class JobInput(Base):
    """
    Maps multiple input files to a single job with defined ordering (for merges / batches).
    """
    __tablename__ = "job_inputs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    job_id = Column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    file_asset_id = Column(String(36), ForeignKey("file_assets.id", ondelete="CASCADE"), nullable=False, index=True)
    ordinal = Column(Integer, default=0, nullable=False)

    job = relationship("Job", back_populates="inputs")
    file_asset = relationship("FileAsset", back_populates="job_inputs")


class Artifact(Base):
    """
    Outputs generated by successful jobs.
    """
    __tablename__ = "artifacts"

    id = Column(String(36), primary_key=True, default=lambda: f"art_{generate_uuid()[:12]}")
    job_id = Column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    owner_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    object_key = Column(String(512), unique=True, nullable=False, index=True)
    filename = Column(String(512), nullable=False)
    mime = Column(String(100), nullable=False)
    bytes = Column(Integer, nullable=False)
    checksum_sha256 = Column(String(64), nullable=False)

    # Derived media properties
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    page_count = Column(Integer, nullable=True)
    compression_ratio = Column(Float, nullable=True)
    savings_percent = Column(Float, nullable=True)
    metadata_json = Column(Text, default="{}", nullable=False)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=True, index=True)

    job = relationship("Job", back_populates="artifacts")


class UsageLedger(Base):
    """
    Usage ledger tracking processing cost and quota units.
    """
    __tablename__ = "usage_ledger"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    owner_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id = Column(String(36), ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True, index=True)
    units = Column(Float, default=1.0, nullable=False)
    unit_type = Column(String(50), default="job", nullable=False)  # job, megabytes, gpu_seconds
    status = Column(String(50), default="settled", nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)


class AuditEvent(Base):
    """
    Security and administrative audit trail.
    """
    __tablename__ = "audit_events"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    actor_id = Column(String(36), nullable=False, index=True)
    action = Column(String(100), nullable=False, index=True)
    resource_type = Column(String(100), nullable=False)
    resource_id = Column(String(100), nullable=False)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    metadata_json = Column(Text, default="{}", nullable=False)
