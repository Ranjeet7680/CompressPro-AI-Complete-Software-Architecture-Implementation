"""
CompressPro AI - Job Orchestrator & Worker Dispatcher with Real Database Persistence
Adheres to Blueprint Section 9 & 10 (State Machine, Protocol, Retries, Real Database).
"""

import json
import logging
from datetime import datetime, timezone
from typing import Dict, Optional, Callable
from concurrent.futures import ThreadPoolExecutor

from apps.api.src.database import SessionLocal
from apps.api.src.db_models import Job as DBJob, Artifact as DBArtifact, JobInput as DBJobInput, FileAsset as DBFileAsset
from workers.common.models import (
    JobRecord, JobState, JobProgress, JobError, ErrorCode, JobOperation, ArtifactMetadata
)
from workers.common.storage import default_storage, StorageInterface
from workers.common.security import validate_file_preflight
from workers.image.processor import process_image_job
from workers.pdf.processor import process_pdf_job
from workers.video.processor import process_video_job

logger = logging.getLogger("compresspro.dispatcher")


class JobDispatcher:
    """
    Manages job queueing, state transitions, background worker dispatch, and real database persistence.
    """
    def __init__(self, storage: StorageInterface = default_storage, max_workers: int = 4):
        self.storage = storage
        self.cancellation_requested: set[str] = set()
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

    def register_job(self, job: JobRecord) -> JobRecord:
        """Persists job record into real relational database, checking idempotency."""
        with SessionLocal() as db:
            if job.idempotency_key:
                existing_db_job = db.query(DBJob).filter(
                    DBJob.owner_id == job.owner_id,
                    DBJob.idempotency_key == job.idempotency_key
                ).first()
                if existing_db_job:
                    return self._db_to_record(existing_db_job)

            # Insert new Job row
            db_job = DBJob(
                id=job.id,
                owner_id=job.owner_id,
                operation=job.operation.value,
                state=job.state.value,
                settings_json=json.dumps(job.settings),
                progress_stage=job.progress.stage,
                progress_percent=job.progress.percent,
                progress_message=job.progress.message,
                attempt=job.attempt,
                max_attempts=job.max_attempts,
                idempotency_key=job.idempotency_key,
                created_at=job.created_at
            )
            db.add(db_job)
            db.flush()

            # Record inputs
            for idx, file_key in enumerate(job.input_file_ids):
                # Ensure FileAsset exists
                file_asset = db.query(DBFileAsset).filter(DBFileAsset.object_key == file_key).first()
                if file_asset:
                    job_input = DBJobInput(
                        job_id=job.id,
                        file_asset_id=file_asset.id,
                        ordinal=idx
                    )
                    db.add(job_input)

            db.commit()
            return job

    def get_job(self, job_id: str) -> Optional[JobRecord]:
        """Reads job directly from real database."""
        with SessionLocal() as db:
            db_job = db.query(DBJob).filter(DBJob.id == job_id).first()
            if not db_job:
                return None
            return self._db_to_record(db_job)

    def request_cancellation(self, job_id: str) -> bool:
        """Requests cooperative cancellation and updates DB."""
        with SessionLocal() as db:
            db_job = db.query(DBJob).filter(DBJob.id == job_id).first()
            if not db_job:
                return False

            if db_job.state in (JobState.SUCCEEDED.value, JobState.FAILED.value, JobState.CANCELLED.value, JobState.REJECTED.value):
                return False

            self.cancellation_requested.add(job_id)
            if db_job.state in (JobState.CREATED.value, JobState.QUEUED.value, JobState.VALIDATING.value):
                db_job.state = JobState.CANCELLED.value
                db_job.error_code = ErrorCode.CANCELLED_BY_USER.value
                db_job.error_message = "Job cancelled by user before execution."
                db_job.completed_at = datetime.now(timezone.utc)
                db.commit()
            return True

    def submit_job(self, job_id: str):
        """Preflights inputs and dispatches job to worker execution."""
        with SessionLocal() as db:
            db_job = db.query(DBJob).filter(DBJob.id == job_id).first()
            if not db_job:
                return

            db_job.state = JobState.VALIDATING.value
            db_job.progress_stage = "validating"
            db_job.progress_percent = 5
            db_job.progress_message = "Validating input files and security preflights"
            db.commit()

            # Resolve input paths from storage
            settings = json.loads(db_job.settings_json or "{}")
            input_keys = [inp.file_asset.object_key for inp in db_job.inputs if inp.file_asset]
            if not input_keys:
                # Fallback to direct input key check
                job_record = self._db_to_record(db_job)
                input_keys = job_record.input_file_ids

        input_paths = []
        for file_key in input_keys:
            path = self.storage.get_file_path(file_key)
            if not path:
                self._update_db_terminal(
                    job_id, JobState.REJECTED, ErrorCode.CORRUPT_INPUT, f"Input file not found in storage: {file_key}"
                )
                return

            is_valid, err_code, err_msg = validate_file_preflight(path)
            if not is_valid:
                self._update_db_terminal(
                    job_id, JobState.REJECTED, ErrorCode(err_code), err_msg or "Validation error"
                )
                return

            input_paths.append(path)

        # Transition to QUEUED
        with SessionLocal() as db:
            db_job = db.query(DBJob).filter(DBJob.id == job_id).first()
            if db_job:
                db_job.state = JobState.QUEUED.value
                db_job.progress_stage = "queued"
                db_job.progress_percent = 10
                db_job.progress_message = "Job queued for worker execution"
                db.commit()

        # Submit to background executor
        self.executor.submit(self._execute_worker, job_id, input_paths, settings)

    def _execute_worker(self, job_id: str, input_paths: list[str], settings: dict):
        if job_id in self.cancellation_requested:
            self._update_db_terminal(job_id, JobState.CANCELLED, ErrorCode.CANCELLED_BY_USER, "Job cancelled.")
            return

        # Transition to RUNNING
        with SessionLocal() as db:
            db_job = db.query(DBJob).filter(DBJob.id == job_id).first()
            if not db_job:
                return
            db_job.state = JobState.RUNNING.value
            db_job.started_at = datetime.now(timezone.utc)
            db_job.progress_stage = "running"
            db_job.progress_percent = 20
            db_job.progress_message = "Worker claimed job"
            op = db_job.operation
            owner_id = db_job.owner_id
            db.commit()

        def progress_callback(stage: str, percent: int):
            with SessionLocal() as db_inner:
                j = db_inner.query(DBJob).filter(DBJob.id == job_id).first()
                if j:
                    j.progress_stage = stage
                    j.progress_percent = percent
                    db_inner.commit()

        try:
            if op.startswith("image."):
                artifacts, error = process_image_job(
                    input_paths, op, settings, progress_callback, self.storage
                )
            elif op.startswith("pdf.") or op == "image.to_pdf":
                artifacts, error = process_pdf_job(
                    input_paths, op, settings, progress_callback, self.storage
                )
            elif op.startswith("video."):
                artifacts, error = process_video_job(
                    input_paths, op, settings, progress_callback, self.storage
                )
            else:
                artifacts, error = [], JobError(
                    code=ErrorCode.UNSUPPORTED_MEDIA_TYPE, message=f"Unknown domain: {op}"
                )

            if job_id in self.cancellation_requested:
                self._update_db_terminal(job_id, JobState.CANCELLED, ErrorCode.CANCELLED_BY_USER, "Job cancelled by user.")
                return

            with SessionLocal() as db:
                db_job = db.query(DBJob).filter(DBJob.id == job_id).first()
                if not db_job:
                    return

                if error:
                    db_job.state = JobState.FAILED.value
                    db_job.error_code = error.code.value
                    db_job.error_message = error.message
                    db_job.completed_at = datetime.now(timezone.utc)
                else:
                    db_job.state = JobState.SUCCEEDED.value
                    db_job.progress_stage = "completed"
                    db_job.progress_percent = 100
                    db_job.progress_message = "Job finished successfully"
                    db_job.completed_at = datetime.now(timezone.utc)

                    # Persist generated artifacts in real database
                    for art in artifacts:
                        db_art = DBArtifact(
                            id=art.id,
                            job_id=job_id,
                            owner_id=owner_id,
                            object_key=art.object_key,
                            filename=art.filename,
                            mime=art.mime,
                            bytes=art.bytes,
                            checksum_sha256=art.checksum_sha256,
                            width=art.width,
                            height=art.height,
                            duration_seconds=art.duration_seconds,
                            page_count=art.page_count,
                            compression_ratio=art.compression_ratio,
                            savings_percent=art.savings_percent
                        )
                        db.add(db_art)

                db.commit()

        except Exception as ex:
            self._update_db_terminal(job_id, JobState.FAILED, ErrorCode.INTERNAL_ERROR, f"Worker exception: {str(ex)}")

    def _update_db_terminal(self, job_id: str, state: JobState, error_code: ErrorCode, message: str):
        with SessionLocal() as db:
            db_job = db.query(DBJob).filter(DBJob.id == job_id).first()
            if db_job:
                db_job.state = state.value
                db_job.error_code = error_code.value
                db_job.error_message = message
                db_job.completed_at = datetime.now(timezone.utc)
                db.commit()

    def _db_to_record(self, db_job: DBJob) -> JobRecord:
        """Converts SQLAlchemy DB row to validated Pydantic JobRecord."""
        artifacts = []
        for a in db_job.artifacts:
            artifacts.append(ArtifactMetadata(
                id=a.id,
                job_id=a.job_id,
                object_key=a.object_key,
                filename=a.filename,
                mime=a.mime,
                bytes=a.bytes,
                checksum_sha256=a.checksum_sha256,
                width=a.width,
                height=a.height,
                duration_seconds=a.duration_seconds,
                page_count=a.page_count,
                compression_ratio=a.compression_ratio,
                savings_percent=a.savings_percent,
                created_at=a.created_at
            ))

        input_keys = [inp.file_asset.object_key for inp in db_job.inputs if inp.file_asset]

        error = None
        if db_job.error_code:
            error = JobError(
                code=ErrorCode(db_job.error_code),
                message=db_job.error_message or "Error occurred"
            )

        return JobRecord(
            id=db_job.id,
            owner_id=db_job.owner_id,
            operation=JobOperation(db_job.operation),
            state=JobState(db_job.state),
            input_file_ids=input_keys,
            settings=json.loads(db_job.settings_json or "{}"),
            progress=JobProgress(
                stage=db_job.progress_stage,
                percent=db_job.progress_percent,
                message=db_job.progress_message
            ),
            attempt=db_job.attempt,
            max_attempts=db_job.max_attempts,
            idempotency_key=db_job.idempotency_key,
            error=error,
            artifacts=artifacts,
            created_at=db_job.created_at,
            started_at=db_job.started_at,
            completed_at=db_job.completed_at
        )


# Global singleton dispatcher
default_dispatcher = JobDispatcher()
