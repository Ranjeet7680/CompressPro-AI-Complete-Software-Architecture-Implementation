# CompressPro AI — Complete Software Architecture & Implementation

An all-in-one image, PDF, and video workspace built for deterministic compression, conversion, editing, and enhancement. Implemented in direct compliance with the **CompressPro AI Architecture Master Blueprint** (v1.0, 15 October 2026).

---

## 🏗️ Architecture & Monorepo Topology

```
.
├── apps/
│   ├── api/                   # FastAPI backend modular monolith (REST API, State Machine, Quotas)
│   │   └── src/
│   │       └── main.py        # Endpoints, upload sessions, job state management, static mount
│   └── web/                   # Responsive web application
│       └── index.html         # High-fidelity dark-purple UI (Tailwind CSS, Drag-Drop, Realtime Progress)
├── workers/                   # Decoupled media processing engines
│   ├── common/
│   │   ├── models.py          # JobState, JobOperation, ErrorCode, ArtifactMetadata Pydantic models
│   │   ├── storage.py         # LocalDiskStorage with path-traversal protection & SHA-256
│   │   ├── security.py        # Magic-byte sniffing, preflight safety, and limit checks
│   │   └── dispatcher.py      # Asynchronous worker queue, routing & cooperative cancellation
│   ├── image/
│   │   └── processor.py       # Pillow: compress, resize, convert, crop, rotate, EXIF stripping
│   ├── pdf/
│   │   └── processor.py       # PyMuPDF (fitz) & PyPDF: compress presets, merge, split, rotate
│   ├── video/
│   │   └── processor.py       # Bundled FFmpeg v7.1: probe, H.264/AAC transcode, trim, resize
│   └── ai/                    # Opt-in GPU inference abstraction
├── packages/
│   └── api-client/            # Shared TypeScript SDK & generated contracts
├── docs/
│   ├── adr/                   # Architecture Decision Records (ADR-001, ADR-002, ADR-003)
│   └── volumes/               # Formal expansion specifications (Volumes 2, 3, and 4)
├── storage_vault/             # Sandboxed object storage (quarantine/, inputs/, artifacts/, temp/)
├── tests/
│   └── test_compresspro.py    # Complete test suite with synthetic fixtures (Image, PDF, Video, API)
└── pyproject.toml             # Project dependency specification
```

---

## 🚀 Quickstart & Running the Application

### 1. Requirements
- Python 3.10+
- Dependencies: `pip install fastapi uvicorn pydantic Pillow pypdf pymupdf imageio-ffmpeg python-multipart pytest httpx`

### 2. Run the Server
Launch the FastAPI server (which automatically serves the responsive Web Workspace at `/`):
```bash
python -m uvicorn apps.api.src.main:app --host 127.0.0.1 --port 8000 --reload
```
Open your browser to: **`http://127.0.0.1:8000`**

### 3. Run the Test Suite
Verify all media processors and end-to-end API workflows:
```bash
pytest tests/test_compresspro.py -v
```

---

## 🛡️ Security & Integrity Principles

1. **Zero-Trust File Ingestion:** Files are sniffed for actual magic bytes (`\xff\xd8\xff` for JPEG, `\x89PNG` for PNG, `%PDF-` for PDF, `ftyp` for MP4). Extensions are never trusted alone.
2. **Safe Argument Invocation:** FFmpeg is invoked via typed argument arrays without shell interpolation (`shell=False`), preventing command injection.
3. **Privacy by Default:** Image EXIF metadata (GPS coordinates, camera serials, timestamps) is stripped automatically unless explicitly preserved.
4. **Output Verification Gate:** Every generated artifact is re-read by an independent decoder to guarantee playable, non-corrupted results before committing state.
5. **Idempotency Protection:** Clients can supply `Idempotency-Key` headers to guarantee duplicate requests never result in duplicate processing.
