"""Setup endpoints for first-run Playwright installation."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter

router = APIRouter()

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _get_chromium_path() -> Path | None:
    """Get the Playwright Chromium cache directory."""
    try:
        from shared import get_playwright_cache_dir

        cache_dir = get_playwright_cache_dir()
        # Check if any chromium directory exists
        if cache_dir.exists():
            for item in cache_dir.iterdir():
                if "chromium" in item.name.lower():
                    return item
    except Exception:
        pass
    return None


@router.get("/setup/chromium-status")
async def chromium_status() -> dict:
    """Check if Chromium is installed for Playwright."""
    chromium_path = _get_chromium_path()
    return {
        "installed": chromium_path is not None,
        "path": str(chromium_path) if chromium_path else None,
    }


@router.post("/setup/install-chromium")
async def install_chromium() -> dict:
    """Install Chromium for Playwright. Streams progress via WebSocket (future)."""
    chromium_path = _get_chromium_path()
    if chromium_path is not None:
        return {"status": "already_installed", "path": str(chromium_path)}

    # Detect frozen mode (PyInstaller)
    is_frozen = getattr(sys, "_MEIPASS", None) is not None

    try:
        if is_frozen:
            # In packaged mode: use Playwright's internal driver
            from playwright._impl._driver import compute_driver_executable

            driver_exe = compute_driver_executable()
            result = subprocess.run(
                [str(driver_exe), "install", "chromium"],
                capture_output=True,
                text=True,
                timeout=300,
            )
        else:
            # In dev mode: use sys.executable
            result = subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                capture_output=True,
                text=True,
                timeout=300,
            )

        if result.returncode == 0:
            return {
                "status": "installed",
                "output": result.stdout[-500:] if result.stdout else "",
            }
        else:
            return {
                "status": "error",
                "error": result.stderr[-500:] if result.stderr else "Unknown error",
            }
    except subprocess.TimeoutExpired:
        return {"status": "error", "error": "Installation timed out"}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}
