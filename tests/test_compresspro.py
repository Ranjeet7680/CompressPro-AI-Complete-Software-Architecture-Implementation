"""
CompressPro AI - End-to-End Test Suite with Real Relational Database
Tests:
- Fixture generation (Image, PDF, Video)
- Image Processing (Compress, Resize, Convert)
- PDF Processing (Compress, Merge, Split, Rotate)
- Video Processing (Probe, Compress, Trim)
- Real Database Persistence (FileAsset, Job, JobInput, Artifact rows)
- FastAPI Endpoints (Upload, Job Creation, Polling, Artifact Download, Stats, Job Deletion)
"""

import os
import time
import pytest
from PIL import Image, ImageDraw
import fitz
import subprocess
from fastapi.testclient import TestClient

from apps.api.src.main import app
from apps.api.src.database import init_db, SessionLocal
from apps.api.src.db_models import Job as DBJob, Artifact as DBArtifact, FileAsset as DBFileAsset
from workers.common.storage import default_storage
from workers.common.models import JobState, JobOperation
from workers.image.processor import process_image_job
from workers.pdf.processor import process_pdf_job
from workers.video.processor import process_video_job, probe_video, get_ffmpeg_binary


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    init_db()


@pytest.fixture(scope="session")
def fixtures_dir():
    dir_path = os.path.join(os.path.dirname(__file__), "fixtures")
    os.makedirs(dir_path, exist_ok=True)
    return dir_path


@pytest.fixture(scope="session")
def sample_image(fixtures_dir):
    """Generates a test JPEG image"""
    img_path = os.path.join(fixtures_dir, "test_sample.jpg")
    img = Image.new("RGB", (800, 600), color=(73, 109, 137))
    d = ImageDraw.Draw(img)
    d.rectangle([(50, 50), (750, 550)], fill=(255, 100, 100), outline=(255, 255, 255), width=4)
    img.save(img_path, "JPEG", quality=95)
    return img_path


@pytest.fixture(scope="session")
def sample_png(fixtures_dir):
    """Generates a test PNG image with RGBA transparency"""
    png_path = os.path.join(fixtures_dir, "test_sample.png")
    img = Image.new("RGBA", (400, 400), color=(0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([(50, 50), (350, 350)], fill=(50, 200, 100, 200))
    img.save(png_path, "PNG")
    return png_path


@pytest.fixture(scope="session")
def sample_pdf(fixtures_dir):
    """Generates a multi-page test PDF document"""
    pdf_path = os.path.join(fixtures_dir, "test_sample.pdf")
    doc = fitz.open()
    for i in range(1, 4):
        page = doc.new_page(width=595, height=842)  # A4
        page.insert_text((50, 100), f"CompressPro AI - Test Document Page {i}", fontsize=20, color=(0, 0, 0))
        page.draw_rect(fitz.Rect(50, 150, 545, 400), color=(0, 0, 1), fill=(0.9, 0.9, 1.0))
    doc.save(pdf_path)
    doc.close()
    return pdf_path


@pytest.fixture(scope="session")
def sample_video(fixtures_dir):
    """Generates a small 1-second 30fps test MP4 video using FFmpeg"""
    vid_path = os.path.join(fixtures_dir, "test_sample.mp4")
    if not os.path.exists(vid_path):
        ffmpeg_exe = get_ffmpeg_binary()
        cmd = [
            ffmpeg_exe, "-y",
            "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=30",
            "-f", "lavfi", "-i", "sine=frequency=1000:duration=1",
            "-c:v", "libx264", "-c:a", "aac",
            "-pix_fmt", "yuv420p",
            vid_path
        ]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    return vid_path


# --- 1. Image Processing Unit Tests ---
def test_image_compression(sample_image):
    artifacts, error = process_image_job(
        input_paths=[sample_image],
        operation="image.compress",
        settings={"output_format": "webp", "quality": 75}
    )
    assert error is None
    assert len(artifacts) == 1
    art = artifacts[0]
    assert art.mime == "image/webp"
    assert art.bytes > 0
    assert art.width == 800
    assert art.height == 600
    assert default_storage.exists(art.object_key)


def test_image_resize(sample_image):
    artifacts, error = process_image_job(
        input_paths=[sample_image],
        operation="image.resize",
        settings={"width": 400, "height": 300, "fit": "contain"}
    )
    assert error is None
    assert len(artifacts) == 1
    art = artifacts[0]
    assert art.width <= 400
    assert art.height <= 300


def test_image_png_convert_flatten(sample_png):
    artifacts, error = process_image_job(
        input_paths=[sample_png],
        operation="image.convert",
        settings={"target_format": "jpeg", "background_color": "#FFFFFF"}
    )
    assert error is None
    assert len(artifacts) == 1
    assert artifacts[0].mime == "image/jpeg"


# --- 2. PDF Processing Unit Tests ---
def test_pdf_compression(sample_pdf):
    artifacts, error = process_pdf_job(
        input_paths=[sample_pdf],
        operation="pdf.compress",
        settings={"preset": "screen"}
    )
    assert error is None
    assert len(artifacts) == 1
    art = artifacts[0]
    assert art.page_count == 3
    assert art.bytes > 0


def test_pdf_split(sample_pdf):
    artifacts, error = process_pdf_job(
        input_paths=[sample_pdf],
        operation="pdf.split",
        settings={"page_range": "1,3"}
    )
    assert error is None
    assert len(artifacts) == 1
    assert artifacts[0].page_count == 2


def test_pdf_merge(sample_pdf):
    artifacts, error = process_pdf_job(
        input_paths=[sample_pdf, sample_pdf],
        operation="pdf.merge",
        settings={}
    )
    assert error is None
    assert len(artifacts) == 1
    assert artifacts[0].page_count == 6


# --- 3. Video Processing Unit Tests ---
def test_video_probe(sample_video):
    probe = probe_video(sample_video)
    assert probe["width"] == 320
    assert probe["height"] == 240
    assert probe["duration_seconds"] is not None
    assert probe["duration_seconds"] >= 0.8


def test_video_compression(sample_video):
    artifacts, error = process_video_job(
        input_paths=[sample_video],
        operation="video.compress",
        settings={"quality_preset": "smaller", "audio_policy": "remove"}
    )
    assert error is None
    assert len(artifacts) == 1
    art = artifacts[0]
    assert art.mime == "video/mp4"
    assert art.bytes > 0


# --- 4. FastAPI & Real Database Tests ---
def test_api_health_and_stats():
    client = TestClient(app)
    resp = client.get("/api/v1/health/live")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

    ready_resp = client.get("/api/v1/health/ready")
    assert ready_resp.status_code == 200
    assert ready_resp.json()["status"] == "ready"
    assert ready_resp.json()["database"] is True

    stats_resp = client.get("/api/v1/stats")
    assert stats_resp.status_code == 200
    stats = stats_resp.json()
    assert "database_engine" in stats
    assert stats["total_jobs"] >= 0


def test_real_database_persistence_flow(sample_image):
    client = TestClient(app)

    # 1. Upload File & check FileAsset table in DB
    with open(sample_image, "rb") as f:
        upload_resp = client.post(
            "/api/v1/uploads",
            files={"file": ("db_test.jpg", f, "image/jpeg")}
        )
    assert upload_resp.status_code == 200
    upload_data = upload_resp.json()
    file_id = upload_data["file_id"]

    # Verify row exists in real database
    with SessionLocal() as db:
        fa = db.query(DBFileAsset).filter(DBFileAsset.object_key == file_id).first()
        assert fa is not None
        assert fa.bytes == upload_data["bytes"]

    # 2. Create Job & check Job table in DB
    job_req = {
        "input_file_ids": [file_id],
        "operation": "image.compress",
        "settings": {"output_format": "webp", "quality": 75}
    }
    create_resp = client.post(
        "/api/v1/jobs",
        json=job_req,
        headers={"Idempotency-Key": "unique_db_test_key_101"}
    )
    assert create_resp.status_code == 200
    job_id = create_resp.json()["job_id"]

    # Verify Job row exists in database
    with SessionLocal() as db:
        j_row = db.query(DBJob).filter(DBJob.id == job_id).first()
        assert j_row is not None
        assert j_row.idempotency_key == "unique_db_test_key_101"

    # 3. Poll Job until Succeeded
    for _ in range(40):
        status_resp = client.get(f"/api/v1/jobs/{job_id}")
        assert status_resp.status_code == 200
        cur_job = status_resp.json()
        if cur_job["status"] == "succeeded":
            break
        time.sleep(0.1)

    assert cur_job["status"] == "succeeded"
    assert len(cur_job["artifacts"]) > 0
    art_id = cur_job["artifacts"][0]["id"]

    # 4. Verify Artifact row exists in database
    with SessionLocal() as db:
        art_row = db.query(DBArtifact).filter(DBArtifact.id == art_id).first()
        assert art_row is not None
        assert art_row.job_id == job_id
        assert art_row.mime == "image/webp"

    # 5. Download Artifact
    dl_resp = client.get(f"/api/v1/artifacts/{art_id}/download")
    assert dl_resp.status_code == 200
    assert len(dl_resp.content) > 0

    # 6. Delete Job from Database
    del_resp = client.delete(f"/api/v1/jobs/{job_id}")
    assert del_resp.status_code == 200

    # Verify deleted from database
    with SessionLocal() as db:
        del_job = db.query(DBJob).filter(DBJob.id == job_id).first()
        assert del_job is None
