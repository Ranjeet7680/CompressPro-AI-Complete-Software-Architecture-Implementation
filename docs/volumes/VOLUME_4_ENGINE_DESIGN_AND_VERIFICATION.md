# CompressPro AI — Volume 4: Processing Engine Design & Verification Matrix

**Document Version:** 1.0  
**Companion to:** Master Architecture Blueprint (Volume 1)

---

## 1. Engine Assignment Matrix

| Domain | Primary Engine | Secondary Engine | Purpose |
|---|---|---|---|
| Image | Pillow (PIL) | libvips (scale) | Deterministic JPEG/PNG/WebP compression, Lanczos resampling, alpha channel flattening |
| PDF | PyMuPDF (fitz) | PyPDF | Deflation, garbage-collection, page manipulation, DPI raster downsampling |
| Video | Bundled FFmpeg v7.1 | ffprobe | Stream probing, H.264/AAC transcode, aspect scaling, duration trimming |
| AI | ONNX Runtime / PyTorch | Isolated GPU Pool | Real-ESRGAN / GFPGAN super-resolution & restoration (opt-in) |

---

## 2. Command & Invocation Safety Guidelines

### 2.1 Argument Array Construction
Never invoke subprocesses with raw string concatenation or `shell=True`.

```python
# PROHIBITED (Vulnerable to command injection):
subprocess.run(f"ffmpeg -i {user_file} -s {user_res} out.mp4", shell=True)

# MANDATED:
cmd = [ffmpeg_exe, "-hide_banner", "-i", validated_path, "-vf", f"scale={w}:{h}", output_path]
subprocess.run(cmd, shell=False, timeout=600)
```

---

## 3. Verification & Acceptance Criteria

Every processor must implement a two-phase execution lifecycle:

```
[INSPECTION / PROBE] ──> [TRANSFORMATION] ──> [OUTPUT VERIFICATION] ──> [COMMIT]
```

### Verification Criteria Checklist:
1. **Readable Container:** The generated output must be re-opened and parsed by the engine (e.g. `Image.open`, `fitz.open`, `probe_video`).
2. **Dimension Match:** If resize was requested, decoded dimensions must equal or fit within configured bounds.
3. **Duration Tolerance:** Trimmed video output duration must match the requested window within $\pm 0.5$ seconds (accounting for GOP keyframe boundaries).
4. **Calculated Metrics:** Output metadata records `bytes`, `checksum_sha256`, `compression_ratio`, and `savings_percent`.
