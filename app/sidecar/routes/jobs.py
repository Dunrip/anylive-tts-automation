from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from models.job import JobStartRequest, JobStatusResponse
from services.job_manager import Job, job_manager
from services.log_streamer import log_streamer

router = APIRouter()


async def _mock_automation(job: Job) -> None:
    total = 3
    for index in range(1, total + 1):
        await asyncio.sleep(0.1)
        version_name = f"version_{index}"
        job.emit_log(f"Processing version {index}/{total}", version=version_name)
        job.emit_progress(index, total, version_name)
    job.emit_log("Automation complete")


@router.post("/jobs", status_code=202)
async def start_job(request: JobStartRequest) -> dict[str, str]:
    options = (
        request.options.model_dump()
        if hasattr(request.options, "model_dump")
        else request.options.dict()
    )

    try:
        job = job_manager.create_job(
            automation_type=request.automation_type,
            config_path=request.config_path,
            csv_path=request.csv_path,
            options=options,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    job.add_log_callback(log_streamer.make_log_callback(job.job_id))
    asyncio.create_task(job_manager.run_job(job, _mock_automation))
    return {"job_id": job.job_id, "status": "accepted"}


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str) -> JobStatusResponse:
    job = job_manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    return job.to_response()


@router.delete("/jobs/{job_id}", status_code=501)
async def cancel_job(job_id: str) -> dict[str, str]:
    return {"detail": "Cancellation not implemented in MVP"}


@router.websocket("/jobs/{job_id}/ws")
async def job_websocket(websocket: WebSocket, job_id: str) -> None:
    await log_streamer.connect(job_id, websocket)
    try:
        while True:
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                await websocket.send_text('{"type":"ping"}')
    except WebSocketDisconnect:
        pass
    finally:
        log_streamer.disconnect(job_id, websocket)
