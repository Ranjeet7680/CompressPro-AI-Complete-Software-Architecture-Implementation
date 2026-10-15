# CompressPro AI — Volume 3: Complete API & Event System Specification

**Document Version:** 1.0  
**Companion to:** Master Architecture Blueprint (Volume 1)

---

## 1. REST Endpoints Overview

Base URL: `/api/v1`

| Method | Endpoint | Purpose | Request Body | Response Envelope |
|---|---|---|---|---|
| `GET` | `/health/live` | Process liveness probe | None | `{"status": "ok", ...}` |
| `GET` | `/health/ready` | Storage & worker readiness | None | `{"status": "ready", ...}` |
| `POST` | `/uploads` | Bounded multipart upload | `multipart/form-data` | `UploadResponse` |
| `POST` | `/jobs` | Enqueue processing job | `CreateJobRequest` | `JobResponse` |
| `GET` | `/jobs/{id}` | Poll job status & progress | None | `JobResponse` |
| `GET` | `/jobs` | List recent jobs | None | `List[JobResponse]` |
| `POST` | `/jobs/{id}/cancel` | Request job cancellation | None | `{"job_id": "...", "status": "cancellation_requested"}` |
| `GET` | `/jobs/{id}/artifacts`| List generated output artifacts | None | `List[ArtifactMetadata]` |
| `GET` | `/artifacts/{id}/download` | Stream binary artifact | None | Binary file stream |

---

## 2. Request & Response JSON Contracts

### 2.1 Job Creation (`POST /api/v1/jobs`)
**Headers:**
- `Idempotency-Key`: UUIDv4 string (optional but recommended)

**Request Body:**
```json
{
  "input_file_ids": ["inputs/5a8b...jpg"],
  "operation": "image.compress",
  "settings": {
    "output_format": "webp",
    "quality": 80,
    "max_width": 1920,
    "max_height": 1080,
    "preserve_metadata": false
  },
  "client_request_id": "req-client-9912"
}
```

**Response (200 OK):**
```json
{
  "job_id": "job_3a8b41cd2e",
  "operation": "image.compress",
  "status": "queued",
  "progress": {
    "stage": "queued",
    "percent": 10,
    "message": "Job queued for worker execution"
  },
  "created_at": "2026-10-15T10:30:00Z",
  "started_at": null,
  "completed_at": null,
  "error": null,
  "artifacts": []
}
```

---

## 3. Error Model & Catalogue

When an error occurs, the API returns a structured RFC 7807 compatible error envelope:

```json
{
  "code": "FILE_TOO_LARGE",
  "message": "File size (280.0 MB) exceeds limit of 250.0 MB.",
  "request_id": "req-01",
  "retryable": false
}
```

### Standard Error Codes:
- `UNSUPPORTED_MEDIA_TYPE`: Sniffed magic bytes do not match supported operations.
- `FILE_TOO_LARGE`: Source file exceeds hard limit of 250 MB.
- `CORRUPT_INPUT`: File header or container tables are unreadable.
- `PASSWORD_REQUIRED`: PDF has an active encryption dictionary.
- `OUTPUT_VALIDATION_FAILED`: Output failed post-processing probe check.
- `CANCELLED_BY_USER`: Cancellation confirmed.
