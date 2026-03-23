from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

router = APIRouter()


class LoginRequest(BaseModel):
    platform: str = "tts"


@router.post("/session/login")
async def trigger_login(request: LoginRequest | None = None) -> dict:
    from server import get_app_data_dir
    from services.job_manager import job_manager
    from shared import (
        set_app_support_dir,
        setup_login,
        SESSION_FILE,
        LIVE_SESSION_FILE,
        LIVE_BROWSER_DATA,
        LIVE_LOGIN_URL,
    )

    if job_manager.is_running:
        raise HTTPException(
            status_code=409, detail="Cannot login while a job is running"
        )

    set_app_support_dir(str(get_app_data_dir()))

    # Determine platform and map to appropriate constants
    platform = request.platform if request else "tts"
    if platform == "live":
        login_url = LIVE_LOGIN_URL
        session_filename = LIVE_SESSION_FILE
        browser_data_subdir = LIVE_BROWSER_DATA
    else:
        # Default to TTS
        login_url = "https://app.anylive.jp"
        session_filename = SESSION_FILE
        browser_data_subdir = "state/browser_data"

    import asyncio

    logger = logging.getLogger(__name__)
    try:
        await setup_login(
            logger,
            login_url=login_url,
            browser_data_subdir=browser_data_subdir,
            session_filename=session_filename,
            gui_mode=True,
        )
    except asyncio.TimeoutError:
        logger.warning("Login timed out — user did not complete login in time")
        return {"status": "timeout"}
    except Exception as exc:
        logger.error("Login failed: %s", exc, exc_info=True)
        return {"status": "error", "error": str(exc)}

    try:
        session_file = get_app_data_dir() / "state" / session_filename.split("/")[-1]
        data = json.loads(session_file.read_text(encoding="utf-8"))
        return {
            "status": "ok",
            "display_name": data.get("display_name"),
            "email": data.get("email"),
        }
    except Exception:
        return {"status": "ok", "display_name": None, "email": None}
