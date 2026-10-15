"""
CompressPro AI - Core Application API with Real Database Persistence
Adheres directly to Master Architecture Blueprint Section 8, 9, 15, and 16.
Features:
- Real Relational Database (SQLAlchemy with SQLite / PostgreSQL)
- Direct FileAsset and Artifact tables mapping
- Bounded file uploads to sandboxed storage vault
- Preflight validation (magic bytes, MIME, size limits)
- Asynchronous job execution with idempotency keys
- Full audit, metrics, and asset deletion endpoints
- Static mounting for responsive web workspace
"""

import os
import uuid
import json
from contextlib import asynccontextmanager
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from fastapi import FastAPI, UploadFile, File, Form, Header, HTTPException, Query, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func

from apps.api.src.database import init_db, get_db, engine
from apps.api.src.db_models import (
    User, FileAsset, Job as DBJob, JobInput as DBJobInput, Artifact as DBArtifact
)
from workers.common.models import (
    JobRecord, JobState, JobOperation, JobProgress, JobError, ErrorCode, ArtifactMetadata
)
from workers.common.storage import default_storage
from workers.common.security import detect_mime_type, validate_file_preflight
from workers.common.dispatcher import default_dispatcher


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables and seed default records
    init_db()
    yield


app = FastAPI(
    title="CompressPro AI API",
    version="1.0.0",
    description="All-in-one image, PDF, and video workspace API with Real Database Persistence",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Request & Response Schemas ---
class UploadResponse(BaseModel):
    file_id: str
    object_key: str
    filename: str
    bytes: int
    detected_mime: str
    status: str


class CreateJobRequest(BaseModel):
    input_file_ids: List[str] = Field(..., description="List of file_ids / object_keys uploaded")
    operation: JobOperation = Field(..., description="Target media operation")
    settings: Dict[str, Any] = Field(default_factory=dict, description="Operation-specific settings")
    client_request_id: Optional[str] = None


class JobResponse(BaseModel):
    job_id: str
    operation: str
    status: str
    progress: JobProgress
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[JobError] = None
    artifacts: List[ArtifactMetadata] = []


class StatsResponse(BaseModel):
    database_engine: str
    total_jobs: int
    total_artifacts: int
    total_source_bytes: int
    total_artifact_bytes: int
    total_bytes_saved: int


# --- Web UI Frontend Serving ---
@app.get("/", response_class=FileResponse)
@app.get("/workspace", response_class=FileResponse)
def serve_web_app():
    """Serves the CompressPro AI responsive web workspace."""
    web_index = os.path.join(os.path.dirname(__file__), "..", "..", "web", "index.html")
    return FileResponse(os.path.abspath(web_index))


# --- Health & Stats Endpoints ---
@app.get("/api/v1/health/live")
def health_live():
    return {
        "status": "ok",
        "service": "CompressPro AI API",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/api/v1/health/ready")
def health_ready(db: Session = Depends(get_db)):
    storage_ok = os.path.exists(str(default_storage.storage_root))
    db_ok = True
    try:
        db.execute(func.now())
    except Exception:
        db_ok = False

    return {
        "status": "ready" if (storage_ok and db_ok) else "unhealthy",
        "storage": storage_ok,
        "database": db_ok,
        "database_dialect": engine.dialect.name
    }


@app.get("/api/v1/stats", response_model=StatsResponse)
def get_system_stats(db: Session = Depends(get_db)):
    """Returns real database aggregated counts and metrics."""
    total_jobs = db.query(DBJob).count()
    total_artifacts = db.query(DBArtifact).count()
    
    src_bytes = db.query(func.coalesce(func.sum(FileAsset.bytes), 0)).scalar() or 0
    art_bytes = db.query(func.coalesce(func.sum(DBArtifact.bytes), 0)).scalar() or 0
    saved = max(0, src_bytes - art_bytes)

    return StatsResponse(
        database_engine=engine.dialect.name,
        total_jobs=total_jobs,
        total_artifacts=total_artifacts,
        total_source_bytes=src_bytes,
        total_artifact_bytes=art_bytes,
        total_bytes_saved=saved
    )


# --- Upload Endpoints (Real DB Persistence) ---
@app.post("/api/v1/uploads", response_model=UploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    category: str = Form(default="inputs"),
    db: Session = Depends(get_db)
):
    """
    Accepts multipart file upload into storage vault and creates FileAsset row in database.
    """
    ext = os.path.splitext(file.filename or "")[1]
    obj_key, sha256_hash, byte_count = default_storage.save_stream(file.file, category=category, extension=ext)

    local_path = default_storage.get_file_path(obj_key)
    detected_mime, family = detect_mime_type(local_path)

    # Preflight check
    is_valid, err_code, err_msg = validate_file_preflight(local_path)
    if not is_valid:
        default_storage.delete(obj_key)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": err_code, "message": err_msg}
        )

    # Persist in real database
    file_asset = FileAsset(
        id=f"file_{uuid.uuid4().hex[:12]}",
        owner_id="guest_default",
        object_key=obj_key,
        original_filename=file.filename or "uploaded_file",
        detected_mime=detected_mime or "application/octet-stream",
        bytes=byte_count,
        checksum_sha256=sha256_hash,
        status="validated",
        created_at=datetime.now(timezone.utc)
    )
    db.add(file_asset)
    db.commit()

    return UploadResponse(
        file_id=obj_key,
        object_key=obj_key,
        filename=file.filename or "uploaded_file",
        bytes=byte_count,
        detected_mime=detected_mime or "application/octet-stream",
        status="validated"
    )


# --- Job Endpoints (Real DB Persistence) ---
@app.post("/api/v1/jobs", response_model=JobResponse)
async def create_job(
    request: CreateJobRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")
):
    """
    Enqueues a processing job with real relational database persistence.
    """
    job_id = f"job_{uuid.uuid4().hex[:12]}"
    job = JobRecord(
        id=job_id,
        owner_id="guest_default",
        operation=request.operation,
        input_file_ids=request.input_file_ids,
        settings=request.settings,
        idempotency_key=idempotency_key
    )

    registered = default_dispatcher.register_job(job)
    if registered.id == job.id:
        default_dispatcher.submit_job(job.id)

    # Fetch latest state from DB
    latest = default_dispatcher.get_job(registered.id) or registered

    return JobResponse(
        job_id=latest.id,
        operation=latest.operation.value,
        status=latest.state.value,
        progress=latest.progress,
        created_at=latest.created_at,
        started_at=latest.started_at,
        completed_at=latest.completed_at,
        error=latest.error,
        artifacts=latest.artifacts
    )


@app.get("/api/v1/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: str):
    """Fetches real-time status and progress directly from real database."""
    job = default_dispatcher.get_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found in database")

    return JobResponse(
        job_id=job.id,
        operation=job.operation.value,
        status=job.state.value,
        progress=job.progress,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        error=job.error,
        artifacts=job.artifacts
    )


@app.get("/api/v1/jobs", response_model=List[JobResponse])
def list_jobs(limit: int = Query(default=20, le=100), db: Session = Depends(get_db)):
    """Lists recent jobs directly from database ordered newest first."""
    db_jobs = db.query(DBJob).order_by(DBJob.created_at.desc()).limit(limit).all()
    results = []
    for dj in db_jobs:
        rec = default_dispatcher._db_to_record(dj)
        results.append(JobResponse(
            job_id=rec.id,
            operation=rec.operation.value,
            status=rec.state.value,
            progress=rec.progress,
            created_at=rec.created_at,
            started_at=rec.started_at,
            completed_at=rec.completed_at,
            error=rec.error,
            artifacts=rec.artifacts
        ))
    return results


@app.post("/api/v1/jobs/{job_id}/cancel")
def cancel_job(job_id: str):
    """Requests cooperative cancellation of a job in the database."""
    success = default_dispatcher.request_cancellation(job_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job cannot be cancelled (not found or already completed)."
        )
    return {"job_id": job_id, "status": "cancellation_requested"}


@app.delete("/api/v1/jobs/{job_id}")
def delete_job(job_id: str, db: Session = Depends(get_db)):
    """Deletes job and cleans up output artifacts from database and storage."""
    db_job = db.query(DBJob).filter(DBJob.id == job_id).first()
    if not db_job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    for art in db_job.artifacts:
        default_storage.delete(art.object_key)

    db.delete(db_job)
    db.commit()
    return {"job_id": job_id, "status": "deleted"}


@app.get("/api/v1/jobs/{job_id}/artifacts", response_model=List[ArtifactMetadata])
def get_job_artifacts(job_id: str, db: Session = Depends(get_db)):
    """Returns artifacts for a job queried from database."""
    db_job = db.query(DBJob).filter(DBJob.id == job_id).first()
    if not db_job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    
    rec = default_dispatcher._db_to_record(db_job)
    return rec.artifacts


@app.get("/api/v1/artifacts/{artifact_id}/download")
def download_artifact(artifact_id: str, db: Session = Depends(get_db)):
    """Streams an artifact file directly by ID using database record."""
    art = db.query(DBArtifact).filter(DBArtifact.id == artifact_id).first()
    if not art:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact record not found in database")

    file_path = default_storage.get_file_path(art.object_key)
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Physical artifact file missing or expired")

    return FileResponse(
        path=file_path,
        media_type=art.mime,
        filename=art.filename
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("apps.api.src.main:app", host="127.0.0.1", port=8000, reload=True)
