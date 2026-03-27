from __future__ import annotations

import asyncio
import inspect
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Optional

_logger = logging.getLogger(__name__)

from models.job import AutomationType, JobProgress, JobStatus, JobStatusResponse


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log_task_exception(task: asyncio.Task[Any]) -> None:
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        _logger.error(
            "Unhandled exception in background task '%s': %s",
            task.get_name(),
            exc,
            exc_info=exc,
        )


def make_job_done_callback(job: Job) -> Callable[[asyncio.Task[Any]], None]:
    def _callback(task: asyncio.Task[Any]) -> None:
        if task.cancelled():
            return
        exc = task.exception()
        if exc is None:
            return
        _logger.error(
            "Unhandled exception in background task for job %s: %s",
            job.job_id,
            exc,
            exc_info=exc,
        )
        if job.status == JobStatus.RUNNING:
            job.status = JobStatus.FAILED
            job.error = str(exc)
            job.finished_at = _now()
            job.emit_status()

    return _callback


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
        self._log_messages: list[dict[str, Any]] = []

    @property
    def is_cancelled(self) -> bool:
        return self.status == JobStatus.CANCELLED

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
        self._log_messages.append(msg)
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
        self._log_messages.append(msg)
        for callback in self._log_callbacks:
            callback(msg)

    def emit_status(self) -> None:
        msg: dict[str, Any] = {
            "type": "status",
            "job_id": self.job_id,
            "status": self.status.value,
        }
        self._log_messages.append(msg)
        for callback in self._log_callbacks:
            callback(msg)

    def to_response(self) -> JobStatusResponse:
        from models.job import LogMessagePayload

        return JobStatusResponse(
            job_id=self.job_id,
            status=self.status,
            progress=self.progress,
            started_at=self.started_at,
            finished_at=self.finished_at,
            error=self.error,
            messages=[LogMessagePayload(**m) for m in self._log_messages],
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
            if job.status == JobStatus.RUNNING:
                job.status = JobStatus.SUCCESS
            else:
                _logger.warning(
                    "Job %s coroutine finished but status is '%s' (expected 'running'); "
                    "preserving externally-set status.",
                    job.job_id,
                    job.status.value,
                )
                job.emit_log("Job was cancelled — status preserved", level="WARN")
        except Exception as exc:
            job.status = JobStatus.FAILED
            job.error = str(exc)
            job.emit_log(f"Job failed: {exc}", level="ERROR")
        finally:
            job.finished_at = _now()
            job.emit_status()
            self._current_job = None
            try:
                from services.history_store import save_run

                save_run(job)
            except Exception as exc:
                _logger.error("Failed to save run to history: %s", exc)
            try:
                from services.log_streamer import log_streamer

                log_streamer.cleanup_job(job.job_id)
            except Exception:
                pass


job_manager = JobManager()
