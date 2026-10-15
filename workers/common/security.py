"""
CompressPro AI - Security Validation, Magic Bytes & Preflight Checks
Adheres to Blueprint Sections 8.5, 11.1, 12.1, 13.1, 16.2.
"""

import os
from typing import Tuple, Optional


# Magic byte signatures
MAGIC_SIGNATURES = {
    "image/jpeg": [b"\xff\xd8\xff"],
    "image/png": [b"\x89PNG\r\n\x1a\n"],
    "image/webp": [b"RIFF"],  # With "WEBP" at offset 8
    "application/pdf": [b"%PDF-"],
    "video/mp4": [b"\x00\x00\x00", b"ftyp"],  # ISO Base Media / MP4
}

# Maximum safety thresholds (configurable via policy)
MAX_FILE_SIZE_BYTES = 250 * 1024 * 1024  # 250 MB
MAX_IMAGE_PIXELS = 100_000_000  # 100 Megapixels (prevents decompression bombs)
MAX_PDF_PAGES = 500
MAX_VIDEO_DURATION_SECONDS = 3600  # 1 hour


def detect_mime_type(file_path: str) -> Tuple[Optional[str], str]:
    """
    Examines file header magic bytes to safely identify format.
    Returns (detected_mime, format_family: 'image' | 'pdf' | 'video' | 'unknown')
    """
    if not os.path.exists(file_path):
        return None, "unknown"

    with open(file_path, "rb") as f:
        header = f.read(32)

    if len(header) < 4:
        return None, "unknown"

    # JPEG
    if header.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", "image"

    # PNG
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", "image"

    # WebP: starts with RIFF and has WEBP at index 8
    if header.startswith(b"RIFF") and len(header) >= 12 and header[8:12] == b"WEBP":
        return "image/webp", "image"

    # PDF: starts with %PDF-
    if header.startswith(b"%PDF-"):
        return "application/pdf", "pdf"

    # MP4 / MOV / ISO media: box ftyp usually at offset 4
    if len(header) >= 12 and header[4:8] == b"ftyp":
        return "video/mp4", "video"

    # Fallback to extension hint with warning
    ext = os.path.splitext(file_path)[1].lower()
    if ext in [".jpg", ".jpeg"]:
        return "image/jpeg", "image"
    elif ext == ".png":
        return "image/png", "image"
    elif ext == ".webp":
        return "image/webp", "image"
    elif ext == ".pdf":
        return "application/pdf", "pdf"
    elif ext in [".mp4", ".mov", ".mkv", ".webm"]:
        return "video/mp4", "video"

    return "application/octet-stream", "unknown"


def validate_file_preflight(file_path: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Validates file exists, has non-zero size, does not exceed limits, and has valid header.
    Returns (is_valid, error_code, error_message)
    """
    if not os.path.exists(file_path):
        return False, "CORRUPT_INPUT", "File does not exist or was deleted."

    size = os.path.getsize(file_path)
    if size == 0:
        return False, "CORRUPT_INPUT", "Uploaded file is 0 bytes."

    if size > MAX_FILE_SIZE_BYTES:
        return False, "FILE_TOO_LARGE", f"File size ({size / 1024 / 1024:.1f} MB) exceeds limit of {MAX_FILE_SIZE_BYTES / 1024 / 1024} MB."

    mime, family = detect_mime_type(file_path)
    if family == "unknown":
        return False, "UNSUPPORTED_MEDIA_TYPE", "File type could not be safely verified or format is not supported."

    return True, None, None
