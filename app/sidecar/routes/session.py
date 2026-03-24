from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter

router = APIRouter()


def _get_session_file(client: str, site: str) -> Path:
    del client, site
    from server import get_app_data_dir

    return get_app_data_dir() / "state" / "session_state.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _status(
    valid: bool,
    client: str,
    site: str,
    display_name: str | None = None,
    email: str | None = None,
) -> dict[str, Any]:
    return {
        "valid": valid,
        "site": site,
        "client": client,
        "checked_at": _now(),
        "display_name": display_name,
        "email": email,
    }


@router.get("/session/{client}/{site}")
async def check_session(client: str, site: str) -> dict[str, Any]:
    session_file = _get_session_file(client, site)
    if not session_file.exists():
        return _status(False, client, site)

    try:
        data = json.loads(session_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return _status(False, client, site)

    valid = data.get("setup_complete", False)
    display_name = data.get("display_name")
    email = data.get("email")
    return _status(valid, client, site, display_name=display_name, email=email)
