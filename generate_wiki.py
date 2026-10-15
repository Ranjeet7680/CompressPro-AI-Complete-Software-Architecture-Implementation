"""
CompressPro AI - 20-Page Technical Wiki Generator with 30+ Mermaid Diagrams
Builds a complete, enterprise-grade GitHub Wiki documentation package.
"""

import os

wiki_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "wiki_test"))
os.makedirs(wiki_dir, exist_ok=True)

pages = {}

# ==============================================================================
# Page 0: Home.md
# ==============================================================================
pages["Home.md"] = """# 📚 CompressPro AI — Architecture & Engineering Wiki

Welcome to the comprehensive technical documentation for **CompressPro AI**, the all-in-one image, PDF, and video workspace.

---

## 🧭 System Ecosystem Overview

```mermaid
flowchart TD
    Client[Web & Mobile Clients] -->|REST / Uploads| Gateway[FastAPI Control Plane]
    Gateway -->|Metadata & Ledgers| Database[(Real DB: SQLite WAL / PostgreSQL)]
    Gateway -->|Enqueues Job| Dispatcher[Async Job Orchestrator]
    
    subgraph Compute [Sandboxed Worker Pool]
        Dispatcher -->|Process Image| W_Img[Image Worker - Pillow]
        Dispatcher -->|Process PDF| W_PDF[PDF Worker - PyMuPDF]
        Dispatcher -->|Process Video| W_Vid[Video Worker - FFmpeg v7.1]
        Dispatcher -->|Enhance| W_AI[AI Worker - GPU Pool]
    end
    
    subgraph Storage [Private Storage Vault]
        Client -->|Direct Stream| S_In[(quarantine / inputs)]
        Compute -->|Commit Artifact| S_Out[(artifacts)]
        Compute -->|Temp Scratch| S_Tmp[(temp)]
    end
```

---

## 📋 Wiki Navigation Index (20 Architectural Modules)

| # | Section / Page | Primary Technical Specifications |
|---|---|---|
| 01 | [[01-System-Architecture]] | Modular monolith design, 4 architectural planes, component boundaries |
| 02 | [[02-Zero-Trust-Security-Model]] | Magic-byte sniffing, threat modeling, sandboxing, injection defense |
| 03 | [[03-Database-Architecture]] | Relational schema, SQLite WAL concurrency, PostgreSQL migration |
| 04 | [[04-Job-State-Machine]] | Deterministic state transitions, retries, and cooperative cancellation |
| 05 | [[05-Image-Processing-Engine]] | Pillow Lanczos downsampling, WebP/PNG/JPEG quality controls, EXIF strip |
| 06 | [[06-PDF-Processing-Engine]] | PyMuPDF stream deflation, garbage collection, merge, split, rotate |
| 07 | [[07-Video-Processing-Engine]] | Bundled FFmpeg v7.1 execution, stream probing, H.264/AAC transcode |
| 08 | [[08-Dual-Verification-Gate]] | Two-pass post-transformation verification and probe checks |
| 09 | [[09-Storage-Vault-Lifecycle]] | Partitioned storage vault, SHA-256 integrity, automated retention |
| 10 | [[10-API-Specification-Contracts]] | REST endpoints, JSON schemas, error catalogues, idempotency keys |
| 11 | [[11-Frontend-UX-Architecture]] | Responsive Single Page App, live stage polling, before/after preview |
| 12 | [[12-Testing-Strategy-280-Catalog]] | 280 test specifications across 9 domains, release gating rules |
| 13 | [[13-AI-Enhancement-Architecture]] | Model registry, opt-in GPU worker pool, evaluation metrics |
| 14 | [[14-Quotas-Ledger-Billing]] | Multi-dimensional resource metering, abuse mitigation, usage ledgers |
| 15 | [[15-Operations-Reliability]] | SLO definitions, health checks, memory budgets, failover runbooks |
| 16 | [[16-Deployment-Vercel-Cloud]] | Serverless Vercel zero-configuration deployment and Docker manifests |
| 17 | [[17-TypeScript-Client-SDK]] | Strongly typed API client SDK, contracts, and frontend consumption |
| 18 | [[18-ADR-Architecture-Decisions]] | Architecture Decision Records (ADR-001, ADR-002, ADR-003) |
| 19 | [[19-Troubleshooting-Runbooks]] | Incident playbooks, queue backlog recovery, stuck job sweeps |
| 20 | [[20-Glossary-Standards]] | Domain terminology, media engineering standards, codec reference |

---

## 🏛️ System Boundary Guarantees

```mermaid
graph LR
    subgraph MUST_DO [Mandatory System Guarantees]
        G1[Sniff Binary Magic Bytes]
        G2[Strip Private EXIF GPS by Default]
        G3[Re-verify Decodable Streams Before Commit]
        G4[Enforce Idempotency on Mutating Jobs]
    end
    subgraph MUST_NOT_DO [Prohibited Practices]
        P1[Trust File Extensions Alone]
        P2[Use shell=True for Command Construction]
        P3[Store Media Blobs in Relational Rows]
        P4[Run Heavy Transcoding on API Thread]
    end
```
"""

# ==============================================================================
# Page 1: 01-System-Architecture.md
# ==============================================================================
pages["01-System-Architecture.md"] = """# 01 — System Architecture

CompressPro AI adopts a **Modular Monolith** architecture for its control plane paired with an **Asynchronous Worker Pool** for compute-intensive media transformations.

---

## 1. The Four Architectural Planes

```mermaid
flowchart TD
    subgraph ClientPlane [1. Client Plane]
        Web[Next.js / Responsive SPA]
        Mobile[Mobile WebView / Android SDK]
    end

    subgraph ControlPlane [2. Control Plane]
        API[FastAPI Modular Gateway]
        Auth[Auth & Quota Guard]
        State[Job State Manager]
    end

    subgraph StoragePlane [3. Storage Plane]
        Vault[Storage Vault: quarantine, inputs, artifacts]
        Relational[(Real DB: SQLite WAL / Postgres)]
    end

    subgraph ComputePlane [4. Compute Plane]
        WorkerImg[Pillow Image Workers]
        WorkerPDF[PyMuPDF PDF Workers]
        WorkerVid[FFmpeg Video Workers]
        WorkerAI[Isolated GPU Inference]
    end

    ClientPlane -->|HTTP / REST| ControlPlane
    ControlPlane -->|Read / Write Metadata| StoragePlane
    ControlPlane -->|Dispatch Task| ComputePlane
    ComputePlane -->|Read Input & Write Output| StoragePlane
```

---

## 2. End-to-End Processing Protocol

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Client as Web Frontend
    participant API as FastAPI Monolith
    participant DB as Relational DB
    participant Dispatcher as Async Dispatcher
    participant Worker as Media Worker
    participant Vault as Storage Vault

    User->>Client: Selects media file & settings
    Client->>API: POST /api/v1/uploads (multipart stream)
    API->>Vault: Write to quarantine & hash SHA-256
    API->>DB: Insert FileAsset row
    API-->>Client: Returns file_id & detected MIME
    Client->>API: POST /api/v1/jobs (Idempotency-Key)
    API->>DB: Insert Job row (CREATED)
    API->>Dispatcher: Submit job_id
    Dispatcher->>DB: Transition state: QUEUED
    Dispatcher->>Worker: Spawn sandboxed process
    Worker->>Vault: Read input & verify magic bytes
    Worker->>Worker: Execute transform & verify output
    Worker->>Vault: Write artifact & hash SHA-256
    Worker->>DB: Commit Artifact & state: SUCCEEDED
    Client->>API: Poll GET /api/v1/jobs/{id}
    API-->>Client: State: SUCCEEDED with Artifact link
    User->>Client: Click Download
```
"""

# ==============================================================================
# Page 2: 02-Zero-Trust-Security-Model.md
# ==============================================================================
pages["02-Zero-Trust-Security-Model.md"] = """# 02 — Zero-Trust Security Model

Media processing engines are high-risk attack surfaces. CompressPro AI enforces a Zero-Trust security perimeter across ingestion, parsing, command construction, and storage.

---

## 1. Multi-Layer Security Perimeter

```mermaid
flowchart TD
    Upload[Raw Ingested Payload] --> Sniff[1. Magic-Byte Sniffer]
    Sniff -->|Invalid Header| Reject1[REJECTED: Unsupported Format]
    Sniff -->|Valid| Bomb[2. Resource Bomb Check]
    Bomb -->|Pixels > 100M or Pages > 500| Reject2[REJECTED: Resource Limit Exceeded]
    Bomb -->|Clean| Sandbox[3. Unprivileged Workspace Allocation]
    
    subgraph ExecutionSandbox [Isolated Execution Sandbox]
        Sandbox --> Run[Non-Root Process]
        Run --> Args[Safe Argument Arrays - No Shell Concatenation]
        Run --> Alarm[Wall-Clock Timeout Alarm]
    end
    
    Alarm -->|Timeout Exceeded| Kill[Terminated with SIGKILL]
    Args --> Verify[4. Independent Probe & Sanity Verification]
    Verify -->|Corrupted Output| Alert[OUTPUT_VALIDATION_FAILED]
    Verify -->|Clean Output| Vault[5. Write to Private Vault with Random UUID]
```

---

## 2. Command Injection Prevention Matrix

```mermaid
flowchart LR
    subgraph UntrustedInput [Untrusted Client Input]
        P1["width: '1920; rm -rf /'"]
    end

    subgraph ValidationBarrier [Pydantic Type & Range Guard]
        V1["int(width) -> Validation Error Blocked!"]
    end

    subgraph SafeInvocation [Safe Subprocess Execution]
        A1["cmd = ['ffmpeg', '-i', in_path, '-vf', 'scale=1920:-2', out_path]"]
        A2["subprocess.run(cmd, shell=False, timeout=600)"]
    end

    UntrustedInput --> ValidationBarrier
    ValidationBarrier --> SafeInvocation
```
"""

# ==============================================================================
# Page 3: 03-Database-Architecture.md
# ==============================================================================
pages["03-Database-Architecture.md"] = """# 03 — Database Architecture

CompressPro AI stores relational state in a schema that supports both embedded SQLite (with Write-Ahead Logging) and PostgreSQL for high-scale multi-replica setups.

---

## 1. Complete Entity-Relationship (ER) Model

```mermaid
erDiagram
    USERS ||--o{ FILE_ASSETS : owns
    USERS ||--o{ JOBS : creates
    JOBS ||--|{ JOB_INPUTS : contains
    FILE_ASSETS ||--o{ JOB_INPUTS : maps_to
    JOBS ||--o{ ARTIFACTS : produces
    USERS ||--o{ USAGE_LEDGER : records
    USERS ||--o{ AUDIT_EVENTS : triggers

    USERS {
        string id PK
        string email UK
        string role
        string status
        datetime created_at
    }

    FILE_ASSETS {
        string id PK
        string owner_id FK
        string object_key UK
        string original_filename
        string detected_mime
        int bytes
        string checksum_sha256
        datetime created_at
    }

    JOBS {
        string id PK
        string owner_id FK
        string operation
        string state
        string settings_json
        string progress_stage
        int progress_percent
        string idempotency_key
        datetime created_at
        datetime completed_at
    }

    ARTIFACTS {
        string id PK
        string job_id FK
        string object_key UK
        string filename
        string mime
        int bytes
        string checksum_sha256
        float savings_percent
        float compression_ratio
    }
```

---

## 2. SQLite WAL High-Concurrency Architecture

```mermaid
flowchart LR
    AppThread1[API Request Thread 1] -->|Concurrent Reads| DB_File[(compresspro.db)]
    AppThread2[API Request Thread 2] -->|Concurrent Reads| DB_File
    WorkerThread[Worker Background Task] -->|Atomic Append| WAL_File[(compresspro.db-wal)]
    WAL_File -.->|Automatic Checkpoint| DB_File
```
"""

# ==============================================================================
# Page 4: 04-Job-State-Machine.md
# ==============================================================================
pages["04-Job-State-Machine.md"] = """# 04 — Job State Machine

All processing jobs adhere to a deterministic 10-state finite state machine governed by atomic transitions and idempotency guards.

---

## 1. Comprehensive State Transition Diagram

```mermaid
stateDiagram-v2
    [*] --> CREATED: Job Registered
    CREATED --> VALIDATING: Ingest Check
    CREATED --> REJECTED: Payload Invalid
    
    VALIDATING --> QUEUED: Signature & Quota OK
    VALIDATING --> REJECTED: Corrupt / Bomb
    
    QUEUED --> RUNNING: Worker Lease Claimed
    QUEUED --> CANCELLED: User Signal
    
    RUNNING --> FINALIZING: Transform Finished
    RUNNING --> CANCELLED: Cooperative Halt
    RUNNING --> FAILED: Engine Exception
    
    FINALIZING --> SUCCEEDED: Output Probe Passed
    FINALIZING --> FAILED: Verification Failed
    
    SUCCEEDED --> EXPIRED: Retention Window Elapsed
    FAILED --> QUEUED: Retry Policy Triggered
    
    REJECTED --> [*]
    CANCELLED --> [*]
    EXPIRED --> [*]
```

---

## 2. Cooperative Cancellation Protocol

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant API as API Handler
    participant DB as Relational DB
    participant Dispatcher as Dispatcher Queue
    participant Worker as Sandboxed Worker

    User->>API: POST /api/v1/jobs/{id}/cancel
    API->>DB: Check state: RUNNING
    API->>Dispatcher: Signal cancellation flag {job_id}
    Dispatcher-->>API: Acknowledged
    API-->>User: {"status": "cancellation_requested"}
    
    loop At Stage Boundary
        Worker->>Dispatcher: Check cancellation flag
        Dispatcher-->>Worker: Flag is ACTIVE
        Worker->>Worker: Terminate subprocess (SIGTERM)
        Worker->>Worker: Delete temporary workspace directory
        Worker->>DB: Update state: CANCELLED
    end
```
"""

# ==============================================================================
# Page 5: 05-Image-Processing-Engine.md
# ==============================================================================
pages["05-Image-Processing-Engine.md"] = """# 05 — Image Processing Engine

Powered by Pillow (PIL) and libvips, the image module delivers deterministic compression, format conversions, and metadata-aware transformations.

---

## 1. Image Processing & Optimization Flow

```mermaid
flowchart TD
    In[Input Image File] --> Decode[Pillow Decoder]
    Decode --> EXIF[Auto-Orient EXIF Orientation]
    EXIF --> OpCheck{Operation Selector}
    
    OpCheck -->|image.compress| Comp[Quantize & WebP/JPEG Quality]
    OpCheck -->|image.resize| Resize[Lanczos Bounded Resampling]
    OpCheck -->|image.convert| Conv[Format & Channel Conversion]
    OpCheck -->|image.crop| Crop[Bounding Box Crop]
    OpCheck -->|image.rotate| Rot[Pixel Rotation 90/180/270]
    
    Comp & Resize & Conv & Crop & Rot --> AlphaCheck{Target Format Has Alpha?}
    AlphaCheck -->|No e.g. JPEG| Flatten[Flatten onto Background Canvas]
    AlphaCheck -->|Yes e.g. PNG/WebP| KeepAlpha[Retain RGBA Channel]
    
    Flatten & KeepAlpha --> StripEXIF[Strip GPS / Private EXIF]
    StripEXIF --> Encode[Save with Format Optimization]
    Encode --> Verify[Re-Decode & Dimension Sanity Gate]
```

---

## 2. Transparency Flattening Architecture

```mermaid
flowchart LR
    RGBA[Source RGBA Image] --> Split[Split Color & Alpha Mask]
    Split --> Canvas[Create Solid RGB Canvas #FFFFFF]
    Canvas --> Paste[Paste Source using Alpha as Mask]
    Paste --> RGB[Output 24-bit JPEG Artifact]
```
"""

# ==============================================================================
# Page 6: 06-PDF-Processing-Engine.md
# ==============================================================================
pages["06-PDF-Processing-Engine.md"] = """# 06 — PDF Processing Engine

The PDF engine relies on PyMuPDF (`fitz`) and PyPDF to handle structural stream optimization, compression presets, and multi-document page operations.

---

## 1. PDF Optimization & Compression Presets

```mermaid
flowchart TD
    InPDF[Source PDF Document] --> CheckEnc{Is Encrypted?}
    CheckEnc -->|Yes| PwdError[Error: PASSWORD_REQUIRED]
    CheckEnc -->|No| Open[Open PyMuPDF Document]
    
    Open --> PresetCheck{Preset Profile}
    PresetCheck -->|Screen| ScreenP[Raster Downsample 72 DPI, Quality 65]
    PresetCheck -->|Balanced| BalP[Raster Downsample 150 DPI, Quality 80]
    PresetCheck -->|Print| PrintP[Preserve 300 DPI Vectors & Fonts]
    
    ScreenP & BalP & PrintP --> Garbage[Garbage Collection Level 4]
    Garbage --> Deflate[Deflate Object Streams]
    Deflate --> Linear[Linearize for Fast Web View]
    Linear --> OutPDF[Write Compressed PDF Artifact]
```

---

## 2. PDF Multi-File Operations

```mermaid
flowchart LR
    subgraph Merging [PDF Merge]
        P1[Doc 1: Pages 1-3]
        P2[Doc 2: Pages 1-5]
        P1 & P2 --> MergeProc[Preserve Sequential Order]
        MergeProc --> MergedOut[Merged Doc: 8 Pages]
    end

    subgraph Splitting [PDF Split & Extract]
        Src[Source Doc: 10 Pages] --> RangeParser[Parse Range '1-3, 7']
        RangeParser --> SplitOut[Extracted Doc: 4 Pages]
    end
```
"""

# ==============================================================================
# Page 7: 07-Video-Processing-Engine.md
# ==============================================================================
pages["07-Video-Processing-Engine.md"] = """# 07 — Video Processing Engine

The video processing engine harnesses bundled FFmpeg v7.1 and ffprobe via strictly constructed argument lists for reliable transcoding and trimming.

---

## 1. Video Probe & Stream Inspection Pipeline

```mermaid
flowchart TD
    InVid[Source Video File] --> Probe[FFmpeg Probe Parser]
    Probe --> Streams{Stream Extractor}
    
    Streams --> VStream[Video Stream: Codec, Width, Height, FPS, Bitrate]
    Streams --> AStream[Audio Stream: Codec, Channels, Sample Rate]
    Streams --> Meta[Container: Duration, Rotation, FastStart]
    
    VStream & AStream & Meta --> Validate{Resource Guard}
    Validate -->|Duration > 1 Hr| ExceedDur[REJECTED: Limit Exceeded]
    Validate -->|Valid Profile| Builder[Build Safe FFmpeg Args]
```

---

## 2. Video Transcoding & Web Optimization

```mermaid
flowchart LR
    InFile[Source Clip] --> PreTrim[Seek -ss and -to]
    PreTrim --> Transcode[libx264 CRF 23 Transcode]
    Transcode --> AudioPol{Audio Setting}
    AudioPol -->|Preserve| AAC[AAC 128kbps Stream]
    AudioPol -->|Remove| Mute[-an Mute Flag]
    
    AAC & Mute --> FastStart[Apply -movflags +faststart]
    FastStart --> PlayableMP4[Web-Playable MP4 Artifact]
```
"""

# ==============================================================================
# Page 8: 08-Dual-Verification-Gate.md
# ==============================================================================
pages["08-Dual-Verification-Gate.md"] = """# 08 — Dual Verification Gate

To prevent corrupted outputs from ever reaching users, CompressPro AI employs a two-pass verification gate that re-inspects outputs before committing job state.

---

## 1. Verification Decision Tree

```mermaid
flowchart TD
    Artifact[Raw Generated Output] --> CheckExists{File Exists on Disk?}
    CheckExists -->|No| Fail1[OUTPUT_VALIDATION_FAILED: Missing]
    CheckExists -->|Yes| CheckSize{Bytes > 0?}
    CheckSize -->|No| Fail2[OUTPUT_VALIDATION_FAILED: Zero Bytes]
    CheckSize -->|Yes| DecodeProbe{Decoder Re-Open Probe}
    
    DecodeProbe -->|Decode Fails| Fail3[OUTPUT_VALIDATION_FAILED: Unreadable Stream]
    DecodeProbe -->|Success| MetricComp{Metric Verification}
    
    MetricComp --> Dims[Verify Width & Height within requested bounds]
    MetricComp --> Dur[Verify Duration matches Trim within 0.5s]
    MetricComp --> Pages[Verify Output Page Count matches Extract Spec]
    
    Dims & Dur & Pages --> Commit[Calculate SHA-256 Checksum & Pass Gate]
```
"""

# ==============================================================================
# Page 9: 09-Storage-Vault-Lifecycle.md
# ==============================================================================
pages["09-Storage-Vault-Lifecycle.md"] = """# 09 — Storage Vault Lifecycle

The private storage vault organizes blobs across isolated prefixes with short-lived access and automated ephemeral cleanup.

---

## 1. Vault Directory Prefix Structure

```mermaid
graph TD
    Vault[storage_vault Root] --> Quar[quarantine/ - Ingested Payloads Before Validation]
    Vault --> Inputs[inputs/ - Validated Preflight Source Files]
    Vault --> Arts[artifacts/ - Verified Output Files Ready for Download]
    Vault --> Temp[temp/ - Sandboxed Workspace Directories]
```

---

## 2. Ephemeral Expiration Sweeper

```mermaid
sequenceDiagram
    autonumber
    participant Sweeper as Scheduled Cleanup Sweeper
    participant DB as Relational DB
    participant Vault as Storage Vault Filesystem

    Note over Sweeper: Runs periodically (e.g. hourly)
    Sweeper->>DB: Query FileAsset & Artifact WHERE expires_at < NOW()
    DB-->>Sweeper: List of expired records
    
    loop For Each Expired Record
        Sweeper->>Vault: Check file existence and delete blob
        Sweeper->>DB: Update status: EXPIRED (or purge row)
    end
```
"""

# ==============================================================================
# Page 10: 10-API-Specification-Contracts.md
# ==============================================================================
pages["10-API-Specification-Contracts.md"] = """# 10 — API Specification Contracts

CompressPro AI exposes a versioned RESTful API under `/api/v1` with JSON contracts and idempotency guarantees.

---

## 1. Upload & Job Execution Flow

```mermaid
sequenceDiagram
    autonumber
    actor Client
    participant API as /api/v1 Gateway
    participant Storage as Storage Vault
    participant Dispatcher as Async Dispatcher

    Client->>API: POST /api/v1/uploads (multipart file)
    API->>Storage: Store blob & hash SHA-256
    API-->>Client: 200 OK {"file_id": "inputs/abc.jpg"}
    
    Client->>API: POST /api/v1/jobs {"input_file_ids": ["inputs/abc.jpg"], "operation": "image.compress"}
    API->>Dispatcher: Enqueue Job
    API-->>Client: 200 OK {"job_id": "job_123", "status": "queued"}
    
    loop Every 500ms
        Client->>API: GET /api/v1/jobs/job_123
        API-->>Client: {"status": "running", "progress": {"percent": 60}}
    end
    
    Client->>API: GET /api/v1/jobs/job_123
    API-->>Client: {"status": "succeeded", "artifacts": [{"id": "art_999"}]}
    
    Client->>API: GET /api/v1/artifacts/art_999/download
    API-->>Client: 200 OK (Binary stream)
```

---

## 2. Idempotency Conflict Resolution

```mermaid
flowchart TD
    Req[POST /api/v1/jobs with Idempotency-Key] --> Lookup{Key Exists in DB?}
    Lookup -->|No| Create[Create & Register New Job]
    Lookup -->|Yes| Compare{Payload Matches Exactly?}
    Compare -->|Yes| ReturnOld[Return Existing Job Record]
    Compare -->|No| Conflict[409 Conflict: Idempotency Key Reused with Different Settings]
```
"""

# ==============================================================================
# Page 11: 11-Frontend-UX-Architecture.md
# ==============================================================================
pages["11-Frontend-UX-Architecture.md"] = """# 11 — Frontend UX Architecture

The frontend is designed as a responsive Single Page Application with accessible controls, real-time stage monitoring, and visual before/after comparators.

---

## 1. Component Hierarchy & State Flow

```mermaid
flowchart TD
    Root[Workspace Root] --> Header[Header & Realtime DB Status Pill]
    Root --> Stats[Aggregated Stats Bar: Jobs, Artifacts, MB Saved]
    Root --> Tabs[Domain Selector Tabs: Image, PDF, Video]
    Root --> Dropzone[Universal Drag & Drop Upload Zone]
    Root --> Config[Dynamic Settings Panel]
    Root --> Progress[Real-Time Progress Card]
    Root --> Results[Results & Visual Comparison Card]
    Root --> History[Database Job Ledger Table]

    Dropzone -->|Files Uploaded| Config
    Config -->|Start Processing| Progress
    Progress -->|Status Succeeded| Results
    Results -->|Update DB| History
```

---

## 2. Real-Time Polling Engine

```mermaid
sequenceDiagram
    autonumber
    participant UI as Frontend State
    participant Timer as Poll Timer (500ms)
    participant API as /api/v1/jobs/{id}

    UI->>Timer: Start polling loop
    loop While status in [validating, queued, running]
        Timer->>API: GET /api/v1/jobs/{activeJobId}
        API-->>UI: Update stage message & progress percentage
        UI->>UI: Animate progress bar width
    end
    Timer->>API: Status is SUCCEEDED
    API-->>UI: Artifact payload
    UI->>Timer: Clear interval
    UI->>UI: Render Before/After Preview & Download Button
```
"""

# ==============================================================================
# Page 12: 12-Testing-Strategy-280-Catalog.md
# ==============================================================================
pages["12-Testing-Strategy-280-Catalog.md"] = """# 12 — Testing Strategy & 280-Case Catalog

Testing is governed by the *200+ Test & Feature Validation Plan*, structuring 280 distinct test specifications across 9 operational domains.

---

## 1. Test Distribution & Coverage Breakdown

```mermaid
pie title 280 Test Specifications
    "Image Processing (IMG-001 - 040)" : 40
    "PDF Processing (PDF-001 - 040)" : 40
    "Video Processing (VID-001 - 040)" : 40
    "API & Orchestration (API-001 - 040)" : 40
    "Frontend & Accessibility (UX-001 - 030)" : 30
    "Operations & Reliability (OPS-001 - 030)" : 30
    "Storage & Retention (STO-001 - 020)" : 20
    "Security & Abuse (SEC-001 - 020)" : 20
    "Account, Quota & Privacy (ACC-001 - 020)" : 20
```

---

## 2. Continuous Integration & Release Gating Flow

```mermaid
flowchart TD
    Commit[Git Commit] --> PR[Pull Request Gate: Unit & Format Tests]
    PR --> Nightly[Nightly Gate: 280 Synthetic Fixture Corpus]
    Nightly --> SecScan[Security Gate: Injection & IDOR Suite]
    SecScan --> Canary[Canary Release: Telemetry & Verification Watch]
    Canary --> Production[Full Production Deployment]
```
"""

# ==============================================================================
# Page 13: 13-AI-Enhancement-Architecture.md
# ==============================================================================
pages["13-AI-Enhancement-Architecture.md"] = """# 13 — AI Enhancement Architecture

AI super-resolution and enhancement are separated from deterministic compression into an opt-in, metered GPU worker pipeline.

---

## 1. Pluggable AI Model Registry Architecture

```mermaid
flowchart TD
    Req[AI Enhancement Request] --> Registry[Model Registry & Version Lookup]
    Registry --> Gate{GPU Capacity & Quota Available?}
    
    Gate -->|No| Fallback[Reject or Offer Standard Non-AI Alternative]
    Gate -->|Yes| Reserve[Atomically Reserve AI Credits]
    
    Reserve --> GPUWorker[Isolated GPU Inference Worker]
    GPUWorker --> PreProc[Tiling & Normalization Preprocessing]
    PreProc --> Model[Real-ESRGAN / GFPGAN Tensor Execution]
    Model --> PostProc[Alpha Re-assembly & Color Match]
    
    PostProc --> Settle[Settle Quota against Actual GPU Seconds]
    Settle --> Out[Deliver AI Enhanced Artifact with Model Version Tag]
```
"""

# ==============================================================================
# Page 14: 14-Quotas-Ledger-Billing.md
# ==============================================================================
pages["14-Quotas-Ledger-Billing.md"] = """# 14 — Quotas, Ledger & Billing

Resource consumption is accounted for via an append-only usage ledger rather than mutable counters.

---

## 1. Multi-Dimensional Resource Metering

```mermaid
flowchart LR
    Job[Media Job Payload] --> M1[Input / Output Bytes Metered]
    Job --> M2[CPU Worker Seconds Metered]
    Job --> M3[GPU Inference Seconds Metered]
    Job --> M4[PDF Page Count Metered]
    
    M1 & M2 & M3 & M4 --> Ledger[(Append-Only Usage Ledger Table)]
    Ledger --> PlanCheck{Plan Entitlements}
    PlanCheck -->|Within Cap| Allow[Job Approved]
    PlanCheck -->|Exceeded| Block[QUOTA_EXCEEDED Error]
```
"""

# ==============================================================================
# Page 15: 15-Operations-Reliability.md
# ==============================================================================
pages["15-Operations-Reliability.md"] = """# 15 — Operations & Reliability

High-availability design principles ensure CompressPro AI degrades gracefully under worker crashes, storage latency, and connection saturation.

---

## 1. Graceful Degradation & Health Circuit

```mermaid
flowchart TD
    Traffic[Incoming Client Traffic] --> HealthProbe{GET /api/v1/health/ready}
    
    HealthProbe -->|DB Down| FailClosed[503 Service Unavailable: No Bypass]
    HealthProbe -->|Storage Healthy| Normal[Full Service Normal Route]
    
    Normal --> WorkerPool{Worker Queue State}
    WorkerPool -->|Worker Crashes| Recover[Worker Lease Heartbeat Timeout -> Auto Requeue]
    WorkerPool -->|GPU Offline| AIOnlyOffline[Deterministic Compress Stays 100% Operational]
```
"""

# ==============================================================================
# Page 16: 16-Deployment-Vercel-Cloud.md
# ==============================================================================
pages["16-Deployment-Vercel-Cloud.md"] = """# 16 — Deployment (Vercel & Cloud)

CompressPro AI provides out-of-the-box support for zero-error serverless deployment on Vercel as well as containerized Docker deployments.

---

## 1. Vercel Serverless Routing Topology

```mermaid
flowchart TD
    VercelEdge[Vercel Global Edge Network] --> Router{vercel.json Route Matching}
    
    Router -->|/api/*| ServerlessFunc[api/index.py Python Serverless Runtime]
    Router -->|/ or /workspace| StaticFrontend[apps/web/index.html Static Workspace]
    
    ServerlessFunc --> WritableTmp[Writable /tmp/ Storage Vault & SQLite WAL]
```

### Vercel Deployment Instructions
1. Connect repository `CompressPro-AI-Complete-Software-Architecture-Implementation` to Vercel.
2. Vercel automatically detects `vercel.json` and `api/index.py`.
3. The build deploys with zero configuration errors!
"""

# ==============================================================================
# Page 17: 17-TypeScript-Client-SDK.md
# ==============================================================================
pages["17-TypeScript-Client-SDK.md"] = """# 17 — TypeScript Client SDK

The `packages/api-client` package provides complete type safety for web, mobile, and third-party integrations.

---

## 1. SDK Type Chain Architecture

```mermaid
flowchart LR
    PydanticSchemas[Backend Pydantic Schemas] --> TypeGen[Shared Contract Specification]
    TypeGen --> TS_SDK[packages/api-client/index.ts]
    TS_SDK --> WebApp[apps/web Next.js / Frontend Application]
    TS_SDK --> MobileApp[Android / Hybrid Application Client]
```

### Example Usage:
```typescript
import { CompressProClient } from '@compresspro/api-client';

const client = new CompressProClient('http://127.0.0.1:8000');
const { file_id } = await client.uploadFile(file);

const job = await client.createJob({
  inputFileIds: [file_id],
  operation: 'image.compress',
  settings: { output_format: 'webp', quality: 80 }
});
```
"""

# ==============================================================================
# Page 18: 18-ADR-Architecture-Decisions.md
# ==============================================================================
pages["18-ADR-Architecture-Decisions.md"] = """# 18 — Architecture Decision Records

Consequential technical decisions are codified in formal Architecture Decision Records (ADRs).

---

## ADR Index

| ADR ID | Title | Status | Core Technical Decision |
|---|---|---|---|
| [[ADR-001]] | Modular Monolith with Isolated Workers | Accepted | Keep API control plane unified while delegating compute to separate worker threads/processes. |
| [[ADR-002]] | Deterministic Media Engine Strategy | Accepted | Standardize on Pillow, PyMuPDF, and static FFmpeg v7.1 with safe argument array construction. |
| [[ADR-003]] | Ephemeral Storage Vault & Retention | Accepted | Enforce privacy-by-default with short-lived expiration and SHA-256 cryptographic checksums. |
"""

# ==============================================================================
# Page 19: 19-Troubleshooting-Runbooks.md
# ==============================================================================
pages["19-Troubleshooting-Runbooks.md"] = """# 19 — Troubleshooting & Runbooks

Operational runbooks for debugging and remediating common production scenarios.

---

## 1. Incident Remediation Flowchart

```mermaid
flowchart TD
    Alert[Incident Alert Triggered] --> Triage{Alert Category}
    
    Triage -->|Queue Backlog > Threshold| QB[Scale Worker Threads & Inspect Stuck Leases]
    Triage -->|Verification Gate Failure Spike| VG[Freeze Encoder Rollout & Rollback Worker Image]
    Triage -->|Database Lock Contention| DB[Verify WAL Mode Active & Synchronous=NORMAL]
    Triage -->|Storage Disk Pressure| SP[Trigger Immediate Ephemeral Sweeper Run]
    
    QB & VG & DB & SP --> Resolve[Verify Metrics Return to Baseline SLO]
```
"""

# ==============================================================================
# Page 20: 20-Glossary-Standards.md
# ==============================================================================
pages["20-Glossary-Standards.md"] = """# 20 — Glossary & Standards

Technical terminology and standards reference for media processing.

---

| Term | Technical Definition | CompressPro AI Context |
|---|---|---|
| **CRF** | Constant Rate Factor | Video encoding quality metric (18 = High, 23 = Balanced, 28 = Small). |
| **Deflate** | Lossless data compression algorithm | Used in PyMuPDF to compress uncompressed PDF streams. |
| **FastStart** | Relocating the `moov` atom to the front of MP4 | Enables instant web playback before full download finishes. |
| **Lanczos** | High-quality sinc interpolation filter | Resampling filter used in Pillow for sharp downsampling. |
| **WAL** | Write-Ahead Logging | SQLite journal mode enabling concurrent reads alongside writes. |
| **Zero-Trust** | Architecture principle assuming all inputs are hostile | Binary magic-byte sniffing and sandbox isolation. |
"""

# ==============================================================================
# Sidebar: _Sidebar.md
# ==============================================================================
pages["_Sidebar.md"] = """### 📚 CompressPro AI Wiki
* **[[Home]]**

---
#### 🏛️ Architecture & Design
* **[[01-System-Architecture]]**
* **[[02-Zero-Trust-Security-Model]]**
* **[[03-Database-Architecture]]**
* **[[04-Job-State-Machine]]**

---
#### ⚙️ Processing Engines
* **[[05-Image-Processing-Engine]]**
* **[[06-PDF-Processing-Engine]]**
* **[[07-Video-Processing-Engine]]**
* **[[08-Dual-Verification-Gate]]**
* **[[09-Storage-Vault-Lifecycle]]**

---
#### 🌐 Interfaces & Contracts
* **[[10-API-Specification-Contracts]]**
* **[[11-Frontend-UX-Architecture]]**
* **[[17-TypeScript-Client-SDK]]**

---
#### 🧪 Testing & Reliability
* **[[12-Testing-Strategy-280-Catalog]]**
* **[[13-AI-Enhancement-Architecture]]**
* **[[14-Quotas-Ledger-Billing]]**
* **[[15-Operations-Reliability]]**

---
#### 🚀 Operations & Deployment
* **[[16-Deployment-Vercel-Cloud]]**
* **[[18-ADR-Architecture-Decisions]]**
* **[[19-Troubleshooting-Runbooks]]**
* **[[20-Glossary-Standards]]**
"""

# ==============================================================================
# Footer: _Footer.md
# ==============================================================================
pages["_Footer.md"] = """---
<p align="center">
  <small>CompressPro AI Documentation • v1.0 Production Baseline • <a href="https://github.com/Ranjeet7680/CompressPro-AI-Complete-Software-Architecture-Implementation">Main Repository</a></small>
</p>
"""

# Write all pages
for filename, content in pages.items():
    dest = os.path.join(wiki_dir, filename)
    with open(dest, "w", encoding="utf-8") as f:
        f.write(content.strip() + "\\n")
    print(f"Generated: {filename}")

print(f"\\nSuccessfully generated {len(pages)} Wiki pages in {wiki_dir}!")
