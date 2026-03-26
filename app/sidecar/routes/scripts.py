"""Script automation endpoints."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from models.job import AutomationType
from services.job_manager import Job, job_manager
from services.log_streamer import log_streamer

if getattr(sys, "frozen", False):
    _REPO_ROOT = Path(sys._MEIPASS)  # type: ignore[attr-defined]
else:
    _REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

router = APIRouter()


class ScriptRunRequest(BaseModel):
    config_path: str
    csv_path: Optional[str] = None
    options: dict[str, Any] = {}


class ScriptDeleteRequest(BaseModel):
    config_path: str
    options: dict[str, Any] = {}


class ScriptReplaceRequest(BaseModel):
    config_path: str
    options: dict[str, Any] = {}


async def _run_script_job(job: Job) -> None:
    from auto_script import run_job  # type: ignore[import]

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
    delete_scripts: bool = bool(opts.get("delete_scripts", False))
    replace_products: bool = bool(opts.get("replace_products", False))
    start_product: Optional[int] = opts.get("start_product")
    limit: Optional[int] = opts.get("limit")
    audio_dir: Optional[str] = opts.get("audio_dir")

    result: dict[str, Any] = await run_job(
        config_path=str(config_path),
        csv_path=csv_path_str,
        headless=headless,
        dry_run=dry_run,
        debug=debug,
        delete_scripts=delete_scripts,
        replace_products=replace_products,
        start_product=start_product,
        limit=limit,
        audio_dir=audio_dir,
        log_callback=log_callback,
        app_support_dir=str(_REPO_ROOT),
    )

    if not result.get("success", False):
        raise RuntimeError(result.get("error") or "Script automation failed")


@router.post("/scripts/run", status_code=202)
async def run_scripts(request: ScriptRunRequest) -> dict[str, str]:
    """Start a Script upload automation job."""
    try:
        job = job_manager.create_job(
            automation_type=AutomationType.SCRIPT,
            config_path=request.config_path,
            csv_path=request.csv_path,
            options=request.options,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    job.add_log_callback(log_streamer.make_log_callback(job.job_id))
    asyncio.create_task(job_manager.run_job(job, _run_script_job))

    return {"job_id": job.job_id, "status": "accepted"}


@router.post("/scripts/delete", status_code=202)
async def delete_scripts(request: ScriptDeleteRequest) -> dict[str, str]:
    """Start a Script delete automation job (no CSV required)."""
    options = {**request.options, "delete_scripts": True}

    try:
        job = job_manager.create_job(
            automation_type=AutomationType.SCRIPT,
            config_path=request.config_path,
            csv_path=None,
            options=options,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    job.add_log_callback(log_streamer.make_log_callback(job.job_id))
    asyncio.create_task(job_manager.run_job(job, _run_script_job))

    return {"job_id": job.job_id, "status": "accepted"}


@router.post("/scripts/replace", status_code=202)
async def replace_scripts(request: ScriptReplaceRequest) -> dict[str, str]:
    """Start a Script replace-products automation job (no CSV required)."""
    options = {**request.options, "replace_products": True}

    try:
        job = job_manager.create_job(
            automation_type=AutomationType.SCRIPT,
            config_path=request.config_path,
            csv_path=None,
            options=options,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    job.add_log_callback(log_streamer.make_log_callback(job.job_id))
    asyncio.create_task(job_manager.run_job(job, _run_script_job))

    return {"job_id": job.job_id, "status": "accepted"}
