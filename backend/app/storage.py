"""
Versioned file storage for jobs.

Layout:
    {storage_dir}/
        {job_id}/
            original/   — the uploaded file, never mutated
            working/    — working copy the agent edits
            result/     — final validated output
"""

import shutil
from pathlib import Path

from app.config import settings


def _job_dir(job_id: str) -> Path:
    return Path(settings.storage_dir) / job_id


def save_upload(job_id: str, filename: str, data: bytes) -> Path:
    """Write the raw upload bytes and return the original file path."""
    original_dir = _job_dir(job_id) / "original"
    original_dir.mkdir(parents=True, exist_ok=True)
    path = original_dir / filename
    path.write_bytes(data)
    return path


def make_working_copy(job_id: str, filename: str) -> Path:
    """Copy the original into the working directory and return its path."""
    src = _job_dir(job_id) / "original" / filename
    working_dir = _job_dir(job_id) / "working"
    working_dir.mkdir(parents=True, exist_ok=True)
    dst = working_dir / filename
    shutil.copy2(src, dst)
    return dst


def get_working_path(job_id: str, filename: str) -> Path:
    return _job_dir(job_id) / "working" / filename


def save_result(job_id: str, filename: str) -> Path:
    """Copy the working file into the result directory and return its path."""
    src = _job_dir(job_id) / "working" / filename
    result_dir = _job_dir(job_id) / "result"
    result_dir.mkdir(parents=True, exist_ok=True)
    dst = result_dir / filename
    shutil.copy2(src, dst)
    return dst


def get_result_path(job_id: str, filename: str) -> Path:
    return _job_dir(job_id) / "result" / filename


def cleanup_job(job_id: str) -> None:
    """Remove all files for a job (call on explicit deletion only)."""
    job_dir = _job_dir(job_id)
    if job_dir.exists():
        shutil.rmtree(job_dir)
