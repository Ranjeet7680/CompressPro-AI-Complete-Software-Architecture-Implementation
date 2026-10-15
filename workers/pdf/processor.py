"""
CompressPro AI - PDF Processing Engine
Adheres to Master Architecture Blueprint Section 12 & Appendix A.
Features:
- PyMuPDF (fitz) & PyPDF powered engine.
- Compression presets: screen, balanced, print.
- Merge, split, rotate, reorder, extract page operations.
- Inter-conversion: Image to PDF, PDF to Images.
- Structural verification and byte savings metrics.
"""

import os
import tempfile
import uuid
from typing import Dict, Any, Tuple, Optional, Callable, List
import fitz  # PyMuPDF
from PIL import Image

from workers.common.models import ArtifactMetadata, JobError, ErrorCode
from workers.common.storage import default_storage, StorageInterface


def parse_page_range(range_str: str, max_pages: int) -> List[int]:
    """
    Parses strings like '1-3, 5, 8-10' into 0-indexed page indices.
    """
    pages: set[int] = set()
    parts = [p.strip() for p in range_str.split(",") if p.strip()]

    for part in parts:
        if "-" in part:
            start_s, end_s = part.split("-", 1)
            start = max(1, int(start_s))
            end = min(max_pages, int(end_s))
            for p in range(start, end + 1):
                pages.add(p - 1)
        else:
            p = int(part)
            if 1 <= p <= max_pages:
                pages.add(p - 1)

    return sorted(list(pages))


def process_pdf_job(
    input_paths: List[str],
    operation: str,
    settings: Dict[str, Any],
    progress_cb: Optional[Callable[[str, int], None]] = None,
    storage: StorageInterface = default_storage
) -> Tuple[List[ArtifactMetadata], Optional[JobError]]:
    """
    Executes a PDF job across input files.
    Returns (artifacts, error).
    """
    if not input_paths:
        return [], JobError(code=ErrorCode.CORRUPT_INPUT, message="No input PDF provided.")

    artifacts: List[ArtifactMetadata] = []

    try:
        if progress_cb:
            progress_cb("validating", 10)

        # ----------------------------------------------------
        # 1. PDF COMPRESS
        # ----------------------------------------------------
        if operation == "pdf.compress":
            input_path = input_paths[0]
            orig_size = os.path.getsize(input_path)
            preset = settings.get("preset", "balanced").lower()

            doc = fitz.open(input_path)
            if doc.is_encrypted:
                return [], JobError(code=ErrorCode.PASSWORD_REQUIRED, message="Password-protected PDFs are not supported.")

            total_pages = len(doc)
            if progress_cb:
                progress_cb("optimizing", 40)

            # PyMuPDF garbage collection, deflate, and image downsampling
            deflate = True
            garbage = 4  # Aggressive unused object removal
            clean = True

            temp_fd, temp_out = tempfile.mkstemp(suffix=".pdf")
            os.close(temp_fd)

            # Preset tuning
            if preset == "screen":
                # Re-compress embedded images with lower quality
                for page in doc:
                    image_list = page.get_images(full=True)
                    for img_info in image_list:
                        xref = img_info[0]
                        try:
                            base_img = doc.extract_image(xref)
                            if base_img and "image" in base_img:
                                # Shrink raster image
                                import io
                                pil_im = Image.open(io.BytesIO(base_img["image"]))
                                if pil_im.width > 1200 or pil_im.height > 1200:
                                    pil_im.thumbnail((1000, 1000), Image.Resampling.LANCZOS)
                                out_buf = io.BytesIO()
                                pil_im.convert("RGB").save(out_buf, format="JPEG", quality=65)
                                # Replace stream
                                doc.update_stream(xref, out_buf.getvalue())
                        except Exception:
                            continue

            doc.save(
                temp_out,
                garbage=garbage,
                deflate=deflate,
                clean=clean,
                linear=True  # Fast web view
            )
            doc.close()

            out_size = os.path.getsize(temp_out)
            # Verify output
            verify_doc = fitz.open(temp_out)
            verify_pages = len(verify_doc)
            verify_doc.close()

            if verify_pages != total_pages or out_size == 0:
                os.remove(temp_out)
                return [], JobError(code=ErrorCode.OUTPUT_VALIDATION_FAILED, message="PDF verification failed after compression.")

            obj_key, sha256_hash, byte_count = storage.save_file(temp_out, category="artifacts")
            os.remove(temp_out)

            savings_pct = round(((orig_size - byte_count) / orig_size) * 100, 2) if orig_size > 0 else 0.0
            ratio = round(byte_count / orig_size, 4) if orig_size > 0 else 1.0

            artifacts.append(ArtifactMetadata(
                id=f"art_{uuid.uuid4().hex[:12]}",
                job_id="",
                object_key=obj_key,
                filename="compressed.pdf",
                mime="application/pdf",
                bytes=byte_count,
                checksum_sha256=sha256_hash,
                page_count=verify_pages,
                compression_ratio=ratio,
                savings_percent=savings_pct
            ))

        # ----------------------------------------------------
        # 2. PDF MERGE
        # ----------------------------------------------------
        elif operation == "pdf.merge":
            if len(input_paths) < 2:
                return [], JobError(code=ErrorCode.CORRUPT_INPUT, message="PDF merge requires at least 2 PDF files.")

            merged_doc = fitz.open()
            total_orig_size = 0

            for idx, p in enumerate(input_paths):
                if progress_cb:
                    progress_cb("merging", int((idx / len(input_paths)) * 70))
                total_orig_size += os.path.getsize(p)
                sub_doc = fitz.open(p)
                if sub_doc.is_encrypted:
                    return [], JobError(code=ErrorCode.PASSWORD_REQUIRED, message=f"Input file #{idx+1} is password protected.")
                merged_doc.insert_pdf(sub_doc)
                sub_doc.close()

            temp_fd, temp_out = tempfile.mkstemp(suffix=".pdf")
            os.close(temp_fd)
            merged_doc.save(temp_out, garbage=3, deflate=True)
            page_count = len(merged_doc)
            merged_doc.close()

            obj_key, sha256_hash, byte_count = storage.save_file(temp_out, category="artifacts")
            os.remove(temp_out)

            artifacts.append(ArtifactMetadata(
                id=f"art_{uuid.uuid4().hex[:12]}",
                job_id="",
                object_key=obj_key,
                filename="merged.pdf",
                mime="application/pdf",
                bytes=byte_count,
                checksum_sha256=sha256_hash,
                page_count=page_count
            ))

        # ----------------------------------------------------
        # 3. PDF SPLIT / EXTRACT
        # ----------------------------------------------------
        elif operation in ("pdf.split", "pdf.extract"):
            input_path = input_paths[0]
            doc = fitz.open(input_path)
            total_pages = len(doc)
            range_str = settings.get("page_range", f"1-{min(total_pages, 5)}")
            selected_indices = parse_page_range(range_str, total_pages)

            if not selected_indices:
                return [], JobError(code=ErrorCode.CORRUPT_INPUT, message="No valid pages selected for split/extract.")

            new_doc = fitz.open()
            for page_idx in selected_indices:
                new_doc.insert_pdf(doc, from_page=page_idx, to_page=page_idx)

            temp_fd, temp_out = tempfile.mkstemp(suffix=".pdf")
            os.close(temp_fd)
            new_doc.save(temp_out, deflate=True)
            new_doc.close()
            doc.close()

            obj_key, sha256_hash, byte_count = storage.save_file(temp_out, category="artifacts")
            os.remove(temp_out)

            artifacts.append(ArtifactMetadata(
                id=f"art_{uuid.uuid4().hex[:12]}",
                job_id="",
                object_key=obj_key,
                filename="extracted.pdf",
                mime="application/pdf",
                bytes=byte_count,
                checksum_sha256=sha256_hash,
                page_count=len(selected_indices)
            ))

        # ----------------------------------------------------
        # 4. PDF ROTATE
        # ----------------------------------------------------
        elif operation == "pdf.rotate":
            input_path = input_paths[0]
            angle = int(settings.get("angle", 90))
            doc = fitz.open(input_path)
            target_pages = settings.get("page_range")  # Optional: specific pages or all

            if target_pages:
                indices = set(parse_page_range(target_pages, len(doc)))
            else:
                indices = set(range(len(doc)))

            for i in indices:
                page = doc[i]
                page.set_rotation((page.rotation + angle) % 360)

            temp_fd, temp_out = tempfile.mkstemp(suffix=".pdf")
            os.close(temp_fd)
            doc.save(temp_out)
            page_count = len(doc)
            doc.close()

            obj_key, sha256_hash, byte_count = storage.save_file(temp_out, category="artifacts")
            os.remove(temp_out)

            artifacts.append(ArtifactMetadata(
                id=f"art_{uuid.uuid4().hex[:12]}",
                job_id="",
                object_key=obj_key,
                filename="rotated.pdf",
                mime="application/pdf",
                bytes=byte_count,
                checksum_sha256=sha256_hash,
                page_count=page_count
            ))

        # ----------------------------------------------------
        # 5. IMAGE TO PDF
        # ----------------------------------------------------
        elif operation == "image.to_pdf":
            doc = fitz.open()
            for img_path in input_paths:
                with Image.open(img_path) as p_img:
                    # Convert to RGB if palette or transparency
                    if p_img.mode in ("RGBA", "LA", "P"):
                        p_img = p_img.convert("RGB")
                    temp_f = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
                    temp_f.close()
                    p_img.save(temp_f.name, format="JPEG", quality=90)

                img_pdf = fitz.open(temp_f.name)
                rect = img_pdf[0].rect
                pdf_bytes = img_pdf.convert_to_pdf()
                img_pdf.close()
                os.remove(temp_f.name)

                img_page = fitz.open("pdf", pdf_bytes)
                doc.insert_pdf(img_page)
                img_page.close()

            temp_fd, temp_out = tempfile.mkstemp(suffix=".pdf")
            os.close(temp_fd)
            doc.save(temp_out, deflate=True)
            page_count = len(doc)
            doc.close()

            obj_key, sha256_hash, byte_count = storage.save_file(temp_out, category="artifacts")
            os.remove(temp_out)

            artifacts.append(ArtifactMetadata(
                id=f"art_{uuid.uuid4().hex[:12]}",
                job_id="",
                object_key=obj_key,
                filename="images_combined.pdf",
                mime="application/pdf",
                bytes=byte_count,
                checksum_sha256=sha256_hash,
                page_count=page_count
            ))

        # ----------------------------------------------------
        # 6. PDF TO IMAGES
        # ----------------------------------------------------
        elif operation == "pdf.to_images":
            input_path = input_paths[0]
            doc = fitz.open(input_path)
            dpi = int(settings.get("dpi", 150))
            fmt = settings.get("format", "png").lower()
            zoom = dpi / 72.0
            matrix = fitz.Matrix(zoom, zoom)

            for i, page in enumerate(doc):
                pix = page.get_pixmap(matrix=matrix)
                temp_fd, temp_out = tempfile.mkstemp(suffix=f".{fmt}")
                os.close(temp_fd)
                pix.save(temp_out)

                obj_key, sha256_hash, byte_count = storage.save_file(temp_out, category="artifacts")
                os.remove(temp_out)

                artifacts.append(ArtifactMetadata(
                    id=f"art_{uuid.uuid4().hex[:12]}",
                    job_id="",
                    object_key=obj_key,
                    filename=f"page_{i + 1}.{fmt}",
                    mime=f"image/{fmt}",
                    bytes=byte_count,
                    checksum_sha256=sha256_hash,
                    width=pix.width,
                    height=pix.height,
                    page_count=1
                ))
            doc.close()

        else:
            return [], JobError(
                code=ErrorCode.UNSUPPORTED_MEDIA_TYPE,
                message=f"Unsupported PDF operation: {operation}"
            )

    except Exception as e:
        return [], JobError(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"PDF processing failed: {str(e)}"
        )

    if progress_cb:
        progress_cb("finalizing", 100)

    return artifacts, None
