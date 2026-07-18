"""
In-memory job store and background job runner.

Job lifecycle:
  pending → running → done
                    → failed
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Optional

from app.docops.session import DocumentSession
from app.models import ChangeEntry, Job, JobStatus
from app.storage import get_working_path, make_working_copy, save_result

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory store
# ---------------------------------------------------------------------------

_store: Dict[str, Job] = {}


def create_job(prompt: str, filename: str) -> Job:
    job = Job(id=str(uuid.uuid4()), prompt=prompt, filename=filename)
    _store[job.id] = job
    return job


def get_job(job_id: str) -> Optional[Job]:
    return _store.get(job_id)


def list_jobs() -> list[Job]:
    return list(_store.values())


def _update(job: Job, **kwargs) -> None:
    for k, v in kwargs.items():
        setattr(job, k, v)
    job.updated_at = datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Background runner
# ---------------------------------------------------------------------------

def run_job(job_id: str) -> None:
    """
    Execute the agent loop for job_id.
    Intended to be called as a FastAPI BackgroundTask.
    """
    job = _store.get(job_id)
    if job is None:
        log.error("run_job: job %s not found", job_id)
        return

    _update(job, status=JobStatus.running)
    log.info("Job %s started — %s", job_id, job.prompt)

    try:
        # Open a working copy of the uploaded file
        working_path = make_working_copy(job_id, job.filename)
        session = DocumentSession(working_path)

        # Import here to avoid circular imports at module load time
        from app.agent.orchestrator import run_agent

        def on_change(tool_name: str, description: str) -> None:
            job.changes.append(ChangeEntry(tool=tool_name, description=description))
            job.updated_at = datetime.now(timezone.utc)
            log.debug("Job %s change: [%s] %s", job_id, tool_name, description)

        run_agent(session, job.prompt, on_change=on_change)

        # Validate — re-open the working file to confirm it isn't corrupt
        _validate(session)

        # Promote working copy to result
        result_path = save_result(job_id, job.filename)
        log.info("Job %s done — result at %s", job_id, result_path)

        _update(
            job,
            status=JobStatus.done,
            result_filename=job.filename,
        )

    except Exception as exc:
        log.exception("Job %s failed: %s", job_id, exc)
        _update(job, status=JobStatus.failed, error=str(exc))


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _validate(session: DocumentSession) -> None:
    """
    Re-open the working file from disk to confirm structural integrity.
    Raises RuntimeError if the file cannot be read back.
    """
    try:
        session.reload()
    except Exception as exc:
        raise RuntimeError(f"Output file failed validation: {exc}") from exc
