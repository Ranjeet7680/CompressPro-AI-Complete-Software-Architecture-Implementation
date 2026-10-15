# CompressPro AI — Volume 2: Functional Requirements & Processing Contracts

**Document Version:** 1.0  
**Status:** Approved Engineering Baseline  
**Companion to:** Master Architecture Blueprint (Volume 1)

---

## 1. Domain Functional Requirements

### 1.1 Image Processing Module
1. **`image.compress`**
   - **Supported Inputs:** JPEG, PNG, WebP (magic-byte validated).
   - **Settings:**
     - `output_format`: `jpeg` | `png` | `webp`
     - `quality`: Integer `1` to `100` (defaults: JPEG 80, WebP 75).
     - `max_width`, `max_height`: Optional integer bounding box with Lanczos downsampling.
     - `preserve_metadata`: Boolean (default `false` strips all EXIF GPS/camera data for privacy).
   - **Behavior:** Never artificially pads bytes. If compressed output exceeds input, reports accurate negative savings.

2. **`image.resize`**
   - **Fit Modes:**
     - `contain`: Preserves aspect ratio, fits entirely within bounding box.
     - `cover`: Crops center to match exact aspect ratio of bounding box.
     - `exact`: Direct stretch to width and height.

3. **`image.convert`**
   - **Alpha Flattening:** When converting transparent PNG/WebP to JPEG, flattens onto configured background color (default `#FFFFFF`).

4. **`image.crop` & `image.rotate`**
   - **Crop:** Bounded `(x, y, width, height)` checked against source dimensions.
   - **Rotate:** Angles `90`, `180`, `270`. Pre-corrects EXIF orientation to prevent double-rotation.

---

### 1.2 PDF Processing Module
1. **`pdf.compress`**
   - **Presets:**
     - `screen`: Aggressively resamples raster images to 72–96 DPI, quality 65.
     - `balanced`: Preserves text and vectors, resamples oversized images to 150 DPI.
     - `print`: High-resolution retention (300 DPI), removes redundant metadata and duplicate font streams.
   - **Optimization:** Object stream deflation, unused object garbage collection (level 4).

2. **`pdf.merge`**
   - Preserves exact array ordering of input PDFs.
   - Validates every sub-document for encryption before modifying output.

3. **`pdf.split` & `pdf.extract`**
   - **Page Range Syntax:** Comma-separated single pages and ranges (e.g. `1-3, 5, 8-10`).
   - 1-indexed for user inputs, internally converted to 0-indexed.

4. **`image.to_pdf` & `pdf.to_images`**
   - `image.to_pdf`: Combines multiple image files into standardized PDF pages with A4/Custom dimensions.
   - `pdf.to_images`: Converts each PDF page into high-resolution PNG or JPEG at selected DPI (default: 150 DPI).

---

### 1.3 Video Processing Module
1. **`video.probe`**
   - Extracts container duration, width, height, fps, bitrate, audio presence, and video codec without decoding full stream.

2. **`video.compress`**
   - **Quality Presets:**
     - `smaller`: CRF 28, medium preset.
     - `balanced`: CRF 23, medium preset.
     - `higher_quality`: CRF 18, slow preset.
   - **Audio Policy:** `preserve` (AAC 128kbps) or `remove` (`-an`).
   - **Target Resolution:** Scaled with `-2` divisor to maintain even pixel boundaries required by H.264.

3. **`video.trim`**
   - Bounded by `start_time` and `end_time` (seconds or `HH:MM:SS`).
   - Web fast-start header flag (`-movflags +faststart`) applied to all exports.

---

## 2. Processing Contract Guarantees

1. **Sandboxed Worker Isolation:** Media engines must execute in temporary unpredictable directories (`storage_vault/temp/<job_id>`).
2. **Output Verification Gate:** Output files must pass independent decoder re-reading before job moves to `SUCCEEDED`.
3. **Idempotency Guarantee:** Jobs bearing the same `Idempotency-Key` return the existing job record without re-encoding.
