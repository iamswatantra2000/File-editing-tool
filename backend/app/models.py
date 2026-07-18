from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    pending = "pending"
    running = "running"
    done = "done"
    failed = "failed"


class JobCreate(BaseModel):
    prompt: str


class ChangeEntry(BaseModel):
    tool: str
    description: str


class Job(BaseModel):
    id: str
    status: JobStatus = JobStatus.pending
    prompt: str
    filename: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    changes: List[ChangeEntry] = []
    error: Optional[str] = None
    result_filename: Optional[str] = None


class JobResponse(BaseModel):
    id: str
    status: JobStatus
    prompt: str
    filename: str
    created_at: datetime
    updated_at: datetime
    changes: List[ChangeEntry]
    error: Optional[str] = None
    result_filename: Optional[str] = None
