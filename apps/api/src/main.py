"""
CompressPro AI - Core Application API (FastAPI)
Adheres to Master Architecture Blueprint Section 8 & 9.
Features:
- Bounded file uploads to quarantine storage
- Preflight validation (magic bytes, MIME, size limits)
- Asynchronous job creation with idempotency keys
- Real-time job polling and cancellation endpoints
- Artifact download streaming with safe content-disposition
- Health checks (liveness and readiness)
"""

import os
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from fastapi import FastAPI, UploadFile, File, Form, Header, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from workers.common.models import (
    JobRecord, JobState, JobOperation, JobProgress, JobError, ErrorCode, ArtifactMetadata
)
from workers.common.storage import default_storage
from workers.common.security import detect_mime_type, validate_file_preflight
from workers.common.dispatcher import default_dispatcher

app = FastAPI(
    title="CompressPro AI API",
    version="1.0.0",
    description="All-in-one image, PDF, and video workspace API"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory Upload Session tracking
upload_sessions: Dict[str, Dict[str, Any]] = {}


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


# --- Web UI Frontend Serving ---
@app.get("/", response_class=FileResponse)
@app.get("/workspace", response_class=FileResponse)
def serve_web_app():
    """Serves the CompressPro AI responsive web workspace."""
    web_index = os.path.join(os.path.dirname(__file__), "..", "..", "web", "index.html")
    return FileResponse(os.path.abspath(web_index))


# --- Health Endpoints ---
@app.get("/api/v1/health/live")
def health_live():
    return {"status": "ok", "service": "CompressPro AI API", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/api/v1/health/ready")
def health_ready():
    storage_ok = os.path.exists(str(default_storage.storage_root))
    return {
        "status": "ready" if storage_ok else "unhealthy",
        "storage": storage_ok,
        "workers": "ready"
    }


# --- Upload Endpoints ---
@app.post("/api/v1/uploads", response_model=UploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    category: str = Form(default="inputs")
):
    """
    Accepts multipart file upload into quarantine/inputs storage.
    Performs initial MIME sniffing and checksumming.
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

    file_id = obj_key  # Using object key as canonical reference
    upload_sessions[file_id] = {
        "file_id": file_id,
        "object_key": obj_key,
        "filename": file.filename or "unknown",
        "bytes": byte_count,
        "checksum": sha256_hash,
        "detected_mime": detected_mime,
        "created_at": datetime.now(timezone.utc)
    }

    return UploadResponse(
        file_id=file_id,
        object_key=obj_key,
        filename=file.filename or "uploaded_file",
        bytes=byte_count,
        detected_mime=detected_mime or "application/octet-stream",
        status="validated"
    )


# --- Job Endpoints ---
@app.post("/api/v1/jobs", response_model=JobResponse)
async def create_job(
    request: CreateJobRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")
):
    """
    Enqueues a processing job for image, PDF, or video.
    Respects Idempotency-Key header to avoid duplicate jobs.
    """
    job_id = f"job_{uuid.uuid4().hex[:12]}"
    job = JobRecord(
        id=job_id,
        operation=request.operation,
        input_file_ids=request.input_file_ids,
        settings=request.settings,
        idempotency_key=idempotency_key
    )

    registered = default_dispatcher.register_job(job)
    if registered.id == job.id:
        # New job, submit to background queue
        await default_dispatcher.submit_job(job.id)

    return JobResponse(
        job_id=registered.id,
        operation=registered.operation.value,
        status=registered.state.value,
        progress=registered.progress,
        created_at=registered.created_at,
        started_at=registered.started_at,
        completed_at=registered.completed_at,
        error=registered.error,
        artifacts=registered.artifacts
    )


@app.get("/api/v1/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: str):
    """Fetches real-time status and progress of a job."""
    job = default_dispatcher.get_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

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
def list_jobs(limit: int = Query(default=20, le=100)):
    """Lists recent jobs sorted newest first."""
    all_jobs = list(default_dispatcher.jobs.values())
    all_jobs.sort(key=lambda j: j.created_at, reverse=True)
    return [
        JobResponse(
            job_id=j.id,
            operation=j.operation.value,
            status=j.state.value,
            progress=j.progress,
            created_at=j.created_at,
            started_at=j.started_at,
            completed_at=j.completed_at,
            error=j.error,
            artifacts=j.artifacts
        )
        for j in all_jobs[:limit]
    ]


@app.post("/api/v1/jobs/{job_id}/cancel")
def cancel_job(job_id: str):
    """Requests cooperative cancellation of a queued or running job."""
    success = default_dispatcher.request_cancellation(job_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job cannot be cancelled (either not found or already completed)."
        )
    return {"job_id": job_id, "status": "cancellation_requested"}


@app.get("/api/v1/jobs/{job_id}/artifacts", response_model=List[ArtifactMetadata])
def get_job_artifacts(job_id: str):
    """Returns generated artifacts for a succeeded job."""
    job = default_dispatcher.get_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job.artifacts


@app.get("/api/v1/artifacts/{artifact_id}/download")
def download_artifact(artifact_id: str):
    """Downloads an artifact file by ID."""
    # Find artifact across jobs
    target_art: Optional[ArtifactMetadata] = None
    for job in default_dispatcher.jobs.values():
        for art in job.artifacts:
            if art.id == artifact_id:
                target_art = art
                break
        if target_art:
            break

    if not target_art:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")

    file_path = default_storage.get_file_path(target_art.object_key)
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Physical artifact file missing or expired")

    return FileResponse(
        path=file_path,
        media_type=target_art.mime,
        filename=target_art.filename
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("apps.api.src.main:app", host="127.0.0.1", port=8000, reload=True)
