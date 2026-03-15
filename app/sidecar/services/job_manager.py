from __future__ import annotations

import inspect
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from models.job import AutomationType, JobProgress, JobStatus, JobStatusResponse


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Job:
    def __init__(
        self,
        job_id: str,
        automation_type: AutomationType,
        config_path: str,
        csv_path: Optional[str],
        options: dict[str, Any],
    ) -> None:
        self.job_id = job_id
        self.automation_type = automation_type
        self.config_path = config_path
        self.csv_path = csv_path
        self.options = options
        self.status = JobStatus.PENDING
        self.progress = JobProgress(current=0, total=0)
        self.started_at = _now()
        self.finished_at: Optional[str] = None
        self.error: Optional[str] = None
        self._log_callbacks: list[Callable[[dict[str, Any]], None]] = []

    def add_log_callback(self, callback: Callable[[dict[str, Any]], None]) -> None:
        self._log_callbacks.append(callback)

    def emit_log(
        self,
        message: str,
        level: str = "INFO",
        version: Optional[str] = None,
    ) -> None:
        msg: dict[str, Any] = {
            "type": "log",
            "level": level,
            "message": message,
            "timestamp": _now(),
            "version": version,
        }
        for callback in self._log_callbacks:
            callback(msg)

    def emit_progress(self, current: int, total: int, version_name: str = "") -> None:
        self.progress = JobProgress(current=current, total=total)
        msg: dict[str, Any] = {
            "type": "progress",
            "current": current,
            "total": total,
            "version_name": version_name,
        }
        for callback in self._log_callbacks:
            callback(msg)

    def emit_status(self) -> None:
        msg: dict[str, Any] = {
            "type": "status",
            "job_id": self.job_id,
            "status": self.status.value,
        }
        for callback in self._log_callbacks:
            callback(msg)

    def to_response(self) -> JobStatusResponse:
        return JobStatusResponse(
            job_id=self.job_id,
            status=self.status,
            progress=self.progress,
            started_at=self.started_at,
            finished_at=self.finished_at,
            error=self.error,
        )


class JobManager:
    def __init__(self) -> None:
        self._current_job: Optional[Job] = None
        self._jobs: dict[str, Job] = {}

    @property
    def is_running(self) -> bool:
        return (
            self._current_job is not None
            and self._current_job.status == JobStatus.RUNNING
        )

    def get_job(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    def create_job(
        self,
        automation_type: AutomationType,
        config_path: str,
        csv_path: Optional[str],
        options: dict[str, Any],
    ) -> Job:
        if self.is_running:
            raise ValueError("A job is already running")

        job_id = str(uuid.uuid4())
        job = Job(
            job_id=job_id,
            automation_type=automation_type,
            config_path=config_path,
            csv_path=csv_path,
            options=options,
        )
        self._jobs[job_id] = job
        self._current_job = job
        return job

    async def run_job(self, job: Job, automation_fn: Callable[..., Any]) -> None:
        job.status = JobStatus.RUNNING
        job.emit_status()
        job.emit_log(f"Starting {job.automation_type.value} automation")

        try:
            result = automation_fn(job)
            if inspect.isawaitable(result):
                await result
            job.status = JobStatus.SUCCESS
        except Exception as exc:
            job.status = JobStatus.FAILED
            job.error = str(exc)
            job.emit_log(f"Job failed: {exc}", level="ERROR")
        finally:
            job.finished_at = _now()
            job.emit_status()
            self._current_job = None


job_manager = JobManager()
