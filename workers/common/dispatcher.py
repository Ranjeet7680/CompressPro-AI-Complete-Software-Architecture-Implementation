"""
CompressPro AI - Job Orchestrator & Worker Dispatcher
Adheres to Blueprint Section 10 (State Machine, Protocol, Retries, Cancellation).
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Optional, Callable
from concurrent.futures import ThreadPoolExecutor

from workers.common.models import JobRecord, JobState, JobProgress, JobError, ErrorCode, JobOperation
from workers.common.storage import default_storage, StorageInterface
from workers.common.security import validate_file_preflight
from workers.image.processor import process_image_job
from workers.pdf.processor import process_pdf_job
from workers.video.processor import process_video_job

logger = logging.getLogger("compresspro.dispatcher")


class JobDispatcher:
    """
    Manages job queueing, state transitions, background worker dispatch, and cancellation.
    """
    def __init__(self, storage: StorageInterface = default_storage, max_workers: int = 4):
        self.storage = storage
        self.jobs: Dict[str, JobRecord] = {}
        self.idempotency_map: Dict[str, str] = {}  # idempotency_key -> job_id
        self.cancellation_requested: set[str] = set()
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

    def register_job(self, job: JobRecord) -> JobRecord:
        """Stores job record and tracks idempotency"""
        if job.idempotency_key:
            if job.idempotency_key in self.idempotency_map:
                existing_id = self.idempotency_map[job.idempotency_key]
                return self.jobs[existing_id]
            self.idempotency_map[job.idempotency_key] = job.id

        self.jobs[job.id] = job
        return job

    def get_job(self, job_id: str) -> Optional[JobRecord]:
        return self.jobs.get(job_id)

    def request_cancellation(self, job_id: str) -> bool:
        job = self.jobs.get(job_id)
        if not job:
            return False

        if job.state in (JobState.SUCCEEDED, JobState.FAILED, JobState.CANCELLED, JobState.REJECTED):
            return False  # Already terminal

        self.cancellation_requested.add(job_id)
        if job.state in (JobState.CREATED, JobState.QUEUED, JobState.VALIDATING):
            job.state = JobState.CANCELLED
            job.error = JobError(code=ErrorCode.CANCELLED_BY_USER, message="Job cancelled by user before execution.")
            job.completed_at = datetime.now(timezone.utc)
        return True

    async def submit_job(self, job_id: str):
        """Dispatches job to async worker execution"""
        job = self.jobs.get(job_id)
        if not job:
            return

        job.state = JobState.VALIDATING
        job.progress = JobProgress(stage="validating", percent=5, message="Validating inputs and quotas")

        # Resolve input paths from storage
        input_paths = []
        for file_key in job.input_file_ids:
            path = self.storage.get_file_path(file_key)
            if not path:
                job.state = JobState.REJECTED
                job.error = JobError(code=ErrorCode.CORRUPT_INPUT, message=f"Input file not found: {file_key}")
                job.completed_at = datetime.now(timezone.utc)
                return

            # Preflight validation
            is_valid, err_code, err_msg = validate_file_preflight(path)
            if not is_valid:
                job.state = JobState.REJECTED
                job.error = JobError(code=ErrorCode(err_code), message=err_msg or "Validation error")
                job.completed_at = datetime.now(timezone.utc)
                return

            input_paths.append(path)

        job.state = JobState.QUEUED
        job.progress = JobProgress(stage="queued", percent=10, message="Job queued for worker execution")

        # Run worker in background thread pool
        self.executor.submit(self._execute_worker, job, input_paths)

    def _execute_worker(self, job: JobRecord, input_paths: list[str]):
        if job.id in self.cancellation_requested:
            job.state = JobState.CANCELLED
            job.completed_at = datetime.now(timezone.utc)
            return

        job.state = JobState.RUNNING
        job.started_at = datetime.now(timezone.utc)
        job.progress = JobProgress(stage="running", percent=20, message="Worker claimed job")

        def progress_callback(stage: str, percent: int):
            job.progress = JobProgress(stage=stage, percent=percent)

        op = job.operation.value

        try:
            # Route to appropriate engine
            if op.startswith("image."):
                artifacts, error = process_image_job(
                    input_paths,
                    op,
                    job.settings,
                    progress_callback,
                    self.storage
                )
            elif op.startswith("pdf.") or op == "image.to_pdf":
                artifacts, error = process_pdf_job(
                    input_paths,
                    op,
                    job.settings,
                    progress_callback,
                    self.storage
                )
            elif op.startswith("video."):
                artifacts, error = process_video_job(
                    input_paths,
                    op,
                    job.settings,
                    progress_callback,
                    self.storage
                )
            else:
                artifacts, error = [], JobError(
                    code=ErrorCode.UNSUPPORTED_MEDIA_TYPE,
                    message=f"Unknown operation domain: {op}"
                )

            # Check if cancelled mid-flight
            if job.id in self.cancellation_requested:
                job.state = JobState.CANCELLED
                job.error = JobError(code=ErrorCode.CANCELLED_BY_USER, message="Job cancelled by user.")
                job.completed_at = datetime.now(timezone.utc)
                return

            if error:
                job.state = JobState.FAILED
                job.error = error
                job.completed_at = datetime.now(timezone.utc)
            else:
                job.state = JobState.SUCCEEDED
                job.progress = JobProgress(stage="completed", percent=100, message="Job finished successfully")
                for art in artifacts:
                    art.job_id = job.id
                job.artifacts = artifacts
                job.completed_at = datetime.now(timezone.utc)

        except Exception as ex:
            job.state = JobState.FAILED
            job.error = JobError(code=ErrorCode.INTERNAL_ERROR, message=f"Worker exception: {str(ex)}")
            job.completed_at = datetime.now(timezone.utc)


# Global singleton dispatcher
default_dispatcher = JobDispatcher()
