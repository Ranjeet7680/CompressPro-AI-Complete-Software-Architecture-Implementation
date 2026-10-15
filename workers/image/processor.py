"""
CompressPro AI - Image Processing Engine
Adheres to Master Architecture Blueprint Section 11 & Appendix A.
Features:
- Deterministic operations: compress, resize, convert, crop, rotate, strip metadata.
- Format support: JPEG, PNG, WebP.
- Perceptual quality controls, transparency handling, and output verification.
"""

import os
import tempfile
import uuid
from typing import Dict, Any, Tuple, Optional, Callable
from PIL import Image, ImageOps

from workers.common.models import ArtifactMetadata, JobError, ErrorCode
from workers.common.storage import default_storage, StorageInterface


def process_image_job(
    input_paths: list[str],
    operation: str,
    settings: Dict[str, Any],
    progress_cb: Optional[Callable[[str, int], None]] = None,
    storage: StorageInterface = default_storage
) -> Tuple[list[ArtifactMetadata], Optional[JobError]]:
    """
    Executes an image job across one or more input files.
    Returns (artifacts, error).
    """
    if not input_paths:
        return [], JobError(code=ErrorCode.CORRUPT_INPUT, message="No input image provided.")

    artifacts: list[ArtifactMetadata] = []

    for idx, input_path in enumerate(input_paths):
        if progress_cb:
            progress_cb("decoding", int((idx / len(input_paths)) * 40))

        try:
            with Image.open(input_path) as img:
                orig_format = img.format or "JPEG"
                orig_size = os.path.getsize(input_path)
                orig_w, orig_h = img.size

                # Auto-orient EXIF rotation if present
                img = ImageOps.exif_transpose(img) or img

                # 1. Operation handling
                if operation == "image.compress":
                    target_format = settings.get("output_format", orig_format).upper()
                    if target_format == "JPG":
                        target_format = "JPEG"
                    quality = int(settings.get("quality", 80))
                    max_w = settings.get("max_width")
                    max_h = settings.get("max_height")

                    if max_w and max_h and (img.width > max_w or img.height > max_h):
                        img.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)

                elif operation == "image.resize":
                    target_w = int(settings.get("width", orig_w))
                    target_h = int(settings.get("height", orig_h))
                    fit_mode = settings.get("fit", "contain")
                    target_format = settings.get("output_format", orig_format).upper()
                    quality = int(settings.get("quality", 85))

                    if fit_mode == "contain":
                        img.thumbnail((target_w, target_h), Image.Resampling.LANCZOS)
                    elif fit_mode == "cover":
                        img = ImageOps.fit(img, (target_w, target_h), method=Image.Resampling.LANCZOS)
                    else:  # exact stretch
                        img = img.resize((target_w, target_h), Image.Resampling.LANCZOS)

                elif operation == "image.convert":
                    target_format = settings.get("target_format", "WEBP").upper()
                    quality = int(settings.get("quality", 85))

                elif operation == "image.crop":
                    x = int(settings.get("x", 0))
                    y = int(settings.get("y", 0))
                    w = int(settings.get("width", orig_w))
                    h = int(settings.get("height", orig_h))
                    target_format = settings.get("output_format", orig_format).upper()
                    quality = int(settings.get("quality", 90))

                    # Validate bounds
                    box = (max(0, x), max(0, y), min(orig_w, x + w), min(orig_h, y + h))
                    img = img.crop(box)

                elif operation == "image.rotate":
                    angle = int(settings.get("angle", 90))
                    target_format = settings.get("output_format", orig_format).upper()
                    quality = int(settings.get("quality", 90))
                    img = img.rotate(-angle, expand=True)

                else:
                    return [], JobError(
                        code=ErrorCode.UNSUPPORTED_MEDIA_TYPE,
                        message=f"Unsupported image operation: {operation}"
                    )

                if progress_cb:
                    progress_cb("encoding", 60)

                # Format normalization & transparency handling
                if target_format == "JPG":
                    target_format = "JPEG"

                if target_format == "JPEG" and img.mode in ("RGBA", "LA", "P"):
                    # Flatten transparency on white background
                    bg_color = settings.get("background_color", "#FFFFFF")
                    background = Image.new("RGB", img.size, bg_color)
                    if img.mode == "P":
                        img = img.convert("RGBA")
                    background.paste(img, mask=img.split()[-1])
                    img = background
                elif img.mode not in ("RGB", "RGBA", "L"):
                    img = img.convert("RGBA" if "A" in img.mode else "RGB")

                # Strip metadata by default unless explicitly asked
                preserve_metadata = settings.get("preserve_metadata", False)

                # Save to temp artifact
                ext = target_format.lower()
                if ext == "jpeg":
                    ext = "jpg"
                temp_fd, temp_out = tempfile.mkstemp(suffix=f".{ext}")
                os.close(temp_fd)

                save_kwargs: Dict[str, Any] = {"format": target_format}
                if target_format in ("JPEG", "WEBP"):
                    save_kwargs["quality"] = quality
                    save_kwargs["optimize"] = True
                elif target_format == "PNG":
                    save_kwargs["optimize"] = True
                    save_kwargs["compress_level"] = 9

                if not preserve_metadata:
                    # Clear EXIF
                    save_kwargs.pop("exif", None)

                img.save(temp_out, **save_kwargs)

                if progress_cb:
                    progress_cb("verifying", 80)

                # 2. Verification step (Section 11.5)
                out_size = os.path.getsize(temp_out)
                with Image.open(temp_out) as verify_img:
                    out_w, out_h = verify_img.size
                    verify_format = verify_img.format

                if out_size == 0 or out_w == 0 or out_h == 0:
                    os.remove(temp_out)
                    return [], JobError(
                        code=ErrorCode.OUTPUT_VALIDATION_FAILED,
                        message="Generated image artifact failed sanity verification."
                    )

                # Store in storage vault
                obj_key, sha256_hash, byte_count = storage.save_file(temp_out, category="artifacts")
                os.remove(temp_out)

                savings_pct = round(((orig_size - byte_count) / orig_size) * 100, 2) if orig_size > 0 else 0.0
                ratio = round(byte_count / orig_size, 4) if orig_size > 0 else 1.0

                mime_map = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
                out_mime = mime_map.get(target_format, f"image/{target_format.lower()}")

                artifact = ArtifactMetadata(
                    id=f"art_{uuid.uuid4().hex[:12]}",
                    job_id="",  # Bound by caller
                    object_key=obj_key,
                    filename=f"processed_{idx + 1}.{ext}",
                    mime=out_mime,
                    bytes=byte_count,
                    checksum_sha256=sha256_hash,
                    width=out_w,
                    height=out_h,
                    compression_ratio=ratio,
                    savings_percent=savings_pct
                )
                artifacts.append(artifact)

        except Exception as e:
            return [], JobError(
                code=ErrorCode.INTERNAL_ERROR,
                message=f"Image processing failed: {str(e)}"
            )

    if progress_cb:
        progress_cb("finalizing", 100)

    return artifacts, None
