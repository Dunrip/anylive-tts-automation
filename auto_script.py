#!/usr/bin/env python3
"""AnyLive Set Live Content Script Automation.

Automates script deletion and audio upload on the 'Set Live Content' tab
of live.app.anylive.jp. Supports --delete-scripts mode to remove all
existing scripts from every product, and upload mode (default) to add
audio files from CSV.
"""

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


from shared import (
    get_session_file_path,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
# Session/browser data are SHARED with auto_faq.py (same site: live.app.anylive.jp).
# Only the last-client tracking file is separate.
SCRIPT_SESSION_FILE = "session_state_faq.json"
SCRIPT_BROWSER_DATA = "browser_data_faq"
SCRIPT_LOGIN_URL = "https://live.app.anylive.jp"
SCRIPT_LAST_CLIENT_FILE = "script_last_client.json"


# ---------------------------------------------------------------------------
# Multi-account session helpers
# ---------------------------------------------------------------------------
def _get_script_session_paths(client: Optional[str]) -> tuple[str, str]:
    """Return (session_filename, browser_data_subdir) for the given client."""
    # Share session/browser_data with auto_faq.py — same site, same auth
    if client:
        return f"session_state_faq_{client}.json", f"browser_data_faq_{client}"
    return SCRIPT_SESSION_FILE, SCRIPT_BROWSER_DATA


def _get_last_script_client() -> Optional[str]:
    path = get_session_file_path(SCRIPT_LAST_CLIENT_FILE)
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f).get("last_client")
        except Exception:
            return None
    return None


def _save_last_script_client(client: str) -> None:
    path = get_session_file_path(SCRIPT_LAST_CLIENT_FILE)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"last_client": client}, f)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class ScriptRow:
    product_number: int
    product_name: str
    script_content: str
    audio_code: str
    row_number: int


@dataclass
class ProductScript:
    product_number: int
    product_name: str
    rows: List[ScriptRow] = field(default_factory=list)
    success: bool = False
    error: Optional[str] = None


@dataclass
class ScriptConfig:
    base_url: str
    audio_dir: str = "downloads"
    audio_extensions: List[str] = field(default_factory=lambda: [".mp3", ".wav"])
    csv_columns: dict = field(
        default_factory=lambda: {
            "product_number": "No.",
            "product_name": "Product Name",
            "script_content": "TH Script",
            "audio_code": "Audio Code",
        }
    )
    csv: str = ""


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------
def load_script_config(
    config_path: str, cli_overrides: Optional[dict] = None
) -> ScriptConfig:
    if not os.path.exists(config_path):
        raise FileNotFoundError(
            f"Config file not found: {config_path}\n"
            f"Please create a config file or use the template at configs/script_template.json"
        )

    with open(config_path, "r", encoding="utf-8") as f:
        config_data = json.load(f)

    if cli_overrides:
        config_data.update(cli_overrides)

    return ScriptConfig(**config_data)


# ---------------------------------------------------------------------------
# Audio file resolution
# ---------------------------------------------------------------------------
def resolve_audio_file(
    audio_code: str,
    product_number: int,
    audio_dir: str,
    extensions: List[str],
    logger: logging.Logger,
) -> Optional[str]:
    """Find the audio file for a given audio_code and product_number.

    Search order:
    1. Subfolder matching ``{zero_padded_number}_*`` (e.g. ``01_Dna_...``)
    2. Flat search in audio_dir root
    """
    if not audio_code:
        return None

    audio_dir_path = Path(audio_dir)
    if not audio_dir_path.exists():
        logger.warning(f"Audio directory not found: {audio_dir}")
        return None

    zero_padded = f"{product_number:02d}"

    # Strategy 1: find subfolder matching product number prefix
    for entry in sorted(audio_dir_path.iterdir()):
        if entry.is_dir() and entry.name.startswith(f"{zero_padded}_"):
            for ext in extensions:
                candidate = entry / f"{audio_code}{ext}"
                if candidate.exists():
                    logger.debug(f"Found audio: {candidate}")
                    return str(candidate.resolve())

    # Strategy 2: flat search in audio_dir root
    for ext in extensions:
        candidate = audio_dir_path / f"{audio_code}{ext}"
        if candidate.exists():
            logger.debug(f"Found audio (flat): {candidate}")
            return str(candidate.resolve())

    logger.warning(
        f"Audio file not found for code '{audio_code}' (product {product_number})"
    )
    return None
