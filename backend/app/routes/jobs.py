"""
Job API routes.

POST  /api/jobs                — upload file + prompt → start job
GET   /api/jobs/{id}           — poll job status
GET   /api/jobs/{id}/result    — download edited file
GET   /api/jobs                — list all jobs (debug)
"""

from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse

from app.jobs import create_job, get_job, list_jobs, run_job
from app.models import JobResponse, JobStatus
from app.storage import get_result_path, save_upload

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

ALLOWED_EXTENSIONS = {".docx", ".xlsx"}


def _check_extension(filename: str) -> str:
    from pathlib import Path
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Upload a .docx or .xlsx file.",
        )
    return ext


# ---------------------------------------------------------------------------
# POST /api/jobs
# ---------------------------------------------------------------------------

@router.post("", status_code=202, response_model=JobResponse)
async def create_job_endpoint(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    prompt: str = Form(...),
):
    """Upload a document and a natural-language prompt. Returns a job id to poll."""
    _check_extension(file.filename)

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    job = create_job(prompt=prompt, filename=file.filename)
    save_upload(job.id, file.filename, data)

    background_tasks.add_task(run_job, job.id)

    return JobResponse(**job.model_dump())


# ---------------------------------------------------------------------------
# GET /api/jobs/{id}
# ---------------------------------------------------------------------------

@router.get("/{job_id}", response_model=JobResponse)
def get_job_endpoint(job_id: str):
    """Poll a job for its current status and change list."""
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return JobResponse(**job.model_dump())


# ---------------------------------------------------------------------------
# GET /api/jobs/{id}/result
# ---------------------------------------------------------------------------

@router.get("/{job_id}/result")
def get_result_endpoint(job_id: str):
    """Download the edited file. Only available when status == done."""
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    if job.status != JobStatus.done:
        raise HTTPException(
            status_code=409,
            detail=f"Job is not done yet (status: {job.status}).",
        )

    result_path = get_result_path(job_id, job.filename)
    if not result_path.exists():
        raise HTTPException(status_code=500, detail="Result file missing on disk.")

    media_type = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        if job.filename.endswith(".docx")
        else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    return FileResponse(
        path=str(result_path),
        media_type=media_type,
        filename=f"edited_{job.filename}",
    )


# ---------------------------------------------------------------------------
# GET /api/jobs  (debug / admin)
# ---------------------------------------------------------------------------

@router.get("", response_model=list[JobResponse])
def list_jobs_endpoint():
    """List all jobs (useful during development)."""
    return [JobResponse(**j.model_dump()) for j in list_jobs()]
