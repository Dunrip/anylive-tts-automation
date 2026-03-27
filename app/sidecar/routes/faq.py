"""FAQ automation endpoint."""

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


class FAQRunRequest(BaseModel):
    config_path: str
    csv_path: str
    options: dict[str, Any] = {}


async def _run_faq_job(job: Job) -> None:
    from auto_faq import run_job  # type: ignore[import]

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

    opts = job.options or {}
    headless: bool = bool(opts.get("headless", True))
    dry_run: bool = bool(opts.get("dry_run", False))
    debug: bool = bool(opts.get("debug", False))
    start_product: Optional[int] = opts.get("start_product")
    limit: Optional[int] = opts.get("limit")
    audio_dir: Optional[str] = opts.get("audio_dir")

    result: dict[str, Any] = await run_job(
        config_path=str(config_path),
        csv_path=csv_path_str or "",
        headless=headless,
        dry_run=dry_run,
        debug=debug,
        start_product=start_product,
        limit=limit,
        audio_dir=audio_dir,
        log_callback=log_callback,
        cancel_check=lambda: job.is_cancelled,
        app_support_dir=str(_REPO_ROOT),
    )

    if not result.get("success", False):
        raise RuntimeError(result.get("error") or "FAQ automation failed")


@router.post("/faq/run", status_code=202)
async def run_faq(request: FAQRunRequest) -> dict[str, str]:
    """Start a FAQ automation job."""
    if not request.csv_path:
        raise HTTPException(
            status_code=422, detail="csv_path is required for FAQ automation"
        )

    try:
        job = job_manager.create_job(
            automation_type=AutomationType.FAQ,
            config_path=request.config_path,
            csv_path=request.csv_path,
            options=request.options,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    job.add_log_callback(log_streamer.make_log_callback(job.job_id))
    task = asyncio.create_task(job_manager.run_job(job, _run_faq_job))
    task.add_done_callback(make_job_done_callback(job))

    return {"job_id": job.job_id, "status": "accepted"}
