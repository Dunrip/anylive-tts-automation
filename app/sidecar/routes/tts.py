"""TTS automation endpoint."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from models.job import AutomationType
from services.job_manager import Job, job_manager, make_job_done_callback
from services.log_streamer import log_streamer

if getattr(sys, "frozen", False):
    _REPO_ROOT = Path(sys._MEIPASS)  # type: ignore[attr-defined]
else:
    _REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

router = APIRouter()


class TTSRunRequest(BaseModel):
    config_path: str
    csv_path: Optional[str] = None
    options: dict[str, Any] = {}


async def _run_tts_job(job: Job) -> None:
    from auto_tts import run_job  # type: ignore[import]

    config_path = Path(job.config_path)
    if not config_path.is_absolute():
        config_path = _REPO_ROOT / config_path

    csv_path_str: Optional[str] = job.csv_path
    if csv_path_str:
        csv_path_obj = Path(csv_path_str)
        if not csv_path_obj.is_absolute():
            csv_path_obj = _REPO_ROOT / csv_path_obj
        csv_path_str = str(csv_path_obj)

    def log_callback(message: str, level: str = "INFO") -> None:
        job.emit_log(message, level=level)

    def progress_callback(current: int, total: int, version_name: str) -> None:
        job.emit_progress(current, total, version_name)

    opts = job.options or {}
    headless: bool = bool(opts.get("headless", True))
    dry_run: bool = bool(opts.get("dry_run", False))
    debug: bool = bool(opts.get("debug", False))
    start_version: Optional[int] = opts.get("start_version")
    limit: Optional[int] = opts.get("limit")

    download: bool = bool(opts.get("download", False))
    replace: bool = bool(opts.get("replace", False))
    flat_mode: bool = bool(opts.get("flat_mode", False))
    no_save: bool = bool(opts.get("no_save", False))
    verify: bool = bool(opts.get("verify", False))

    version_filter_raw: Optional[str] = opts.get("version_filter")
    version_filter: Optional[set[int]] = None
    if version_filter_raw:
        from auto_tts import parse_version_spec  # type: ignore[import]

        version_filter = parse_version_spec(version_filter_raw)

    result: dict[str, Any] = await run_job(
        config_path=str(config_path),
        csv_path=csv_path_str or "",
        headless=headless,
        dry_run=dry_run,
        debug=debug,
        start_version=start_version,
        limit=limit,
        download=download,
        replace=replace,
        version_filter=version_filter,
        flat_mode=flat_mode,
        no_save=no_save,
        verify=verify,
        log_callback=log_callback,
        progress_callback=progress_callback,
        cancel_check=lambda: job.is_cancelled,
        app_support_dir=str(_REPO_ROOT),
    )

    if not result.get("success", False):
        raise RuntimeError(result.get("error") or "TTS automation failed")


@router.post("/tts/run", status_code=202)
async def run_tts(request: TTSRunRequest) -> dict[str, str]:
    """Start a TTS automation job."""
    is_download = (
        bool(request.options.get("download", False))
        if isinstance(request.options, dict)
        else False
    )
    if not request.csv_path and not is_download:
        raise HTTPException(
            status_code=422,
            detail="csv_path is required for TTS automation (except download mode)",
        )

    try:
        job = job_manager.create_job(
            automation_type=AutomationType.TTS,
            config_path=request.config_path,
            csv_path=request.csv_path,
            options=request.options,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    job.add_log_callback(log_streamer.make_log_callback(job.job_id))
    task = asyncio.create_task(job_manager.run_job(job, _run_tts_job))
    task.add_done_callback(make_job_done_callback(job))

    return {"job_id": job.job_id, "status": "accepted"}
