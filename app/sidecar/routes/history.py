from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException

from services import history_store

router = APIRouter()


@router.get("/history")
async def list_history(
    limit: int = 50,
    offset: int = 0,
    type: Optional[str] = None,
) -> list[dict]:
    return history_store.get_runs(limit=limit, offset=offset, type_filter=type)


@router.get("/history/{run_id}")
async def get_history_run(run_id: str) -> dict:
    run = history_store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return run
