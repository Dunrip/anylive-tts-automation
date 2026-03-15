"""Job state and API models."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AutomationType(str, Enum):
    TTS = "tts"
    FAQ = "faq"
    SCRIPT = "script"


class AutomationOptions(BaseModel):
    headless: bool = False
    dry_run: bool = False
    debug: bool = False
    start_version: Optional[int] = None
    start_product: Optional[int] = None
    limit: Optional[int] = None
    audio_dir: Optional[str] = None
    delete_scripts: bool = False


class JobStartRequest(BaseModel):
    automation_type: AutomationType
    config_path: str
    csv_path: Optional[str] = None
    options: AutomationOptions = AutomationOptions()


class JobProgress(BaseModel):
    current: int = 0
    total: int = 0


class JobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    progress: JobProgress
    started_at: str
    finished_at: Optional[str] = None
    error: Optional[str] = None
