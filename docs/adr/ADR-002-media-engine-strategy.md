# ADR-002: Deterministic Media Engine Strategy & Sandboxing

## Status
Accepted

## Context
Media parsing represents one of the most vulnerable attack vectors in server systems (decompression bombs, malformed container headers, heap buffer overflows). Relying on experimental libraries or untrusted user scripts poses severe security risks.

## Decision
1. For Images: Use Pillow with strict decompression limits (`Image.MAX_IMAGE_PIXELS = 100_000_000`).
2. For PDFs: Use PyMuPDF (`fitz`) and PyPDF for direct C-level parsing with strict page count and memory bounding.
3. For Video: Bundle verified static FFmpeg v7.1 binaries, invoking via typed argument lists without shell interpolation.
4. Separate AI upscaling/enhancement into a strictly opt-in, metered pipeline to prevent unexpected costs or false fidelity expectations.

## Consequences
- Guaranteed reproducibility across all client platforms.
- Complete protection against shell command injection.
- Consistent encoding quality metrics (SSIM, PSNR, byte savings).
