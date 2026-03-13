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

import pandas as pd

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
# CSV parsing
# ---------------------------------------------------------------------------
def parse_script_csv(
    df: pd.DataFrame, config: ScriptConfig, logger: logging.Logger
) -> List[ProductScript]:
    """Parse script CSV into ProductScript objects.

    Follows the same pattern as parse_faq_csv:
    - Auto-detects headers from first data row if needed
    - Forward-fills product_number and product_name
    - Filters rows with either script_content OR audio_code
    - Filters out products with product_number < 1
    - Groups by product_number
    """
    col_product_no = config.csv_columns.get("product_number", "No.")
    col_product_name = config.csv_columns.get("product_name", "Product Name")
    col_script = config.csv_columns.get("script_content", "TH Script")
    col_audio = config.csv_columns.get("audio_code", "Audio Code")

    # Handle empty DataFrame
    if len(df) == 0:
        logger.info("Valid script rows: 0")
        logger.info("Total script rows: 0")
        logger.info("Found 0 unique products")
        return []

    # Header detection (same pattern as auto_faq.py)
    required_cols = {col_product_no, col_product_name, col_script, col_audio}
    actual_cols = set(str(c).strip() for c in df.columns)

    if required_cols.issubset(actual_cols):
        logger.debug(f"CSV headers already parsed correctly: {list(df.columns)}")
    else:
        first_row_values = [str(v).strip() for v in df.iloc[0] if pd.notna(v)]
        first_row_set = set(first_row_values)

        header_in_first_row = required_cols.issubset(first_row_set) or any(
            v.lower() in {col_product_name.lower(), "product name"}
            for v in first_row_values
        )

        if header_in_first_row:
            new_header = list(df.iloc[0])
            df = df[1:].reset_index(drop=True)
            df.columns = [
                str(v).strip() if pd.notna(v) else f"col_{i}"
                for i, v in enumerate(new_header)
            ]
            logger.debug(
                f"Header auto-detected from first data row: {list(df.columns)}"
            )
        else:
            logger.warning(
                f"Could not find expected columns {required_cols} in CSV. "
                f"Actual columns: {list(df.columns)}. Proceeding anyway."
            )

    # Filter header-like rows
    df = df[df[col_product_name] != col_product_name]

    # Forward-fill product_number and product_name
    df[col_product_name] = df[col_product_name].replace("", pd.NA)
    df[col_product_name] = df[col_product_name].ffill()
    df[col_product_no] = df[col_product_no].replace("", pd.NA)
    df[col_product_no] = df[col_product_no].ffill()

    # Filter rows that have either script_content or audio_code
    valid_rows = df[df[col_script].notna() | df[col_audio].notna()]
    logger.info(f"Valid script rows: {len(valid_rows)}")

    script_rows: List[ScriptRow] = []
    for idx, row in valid_rows.iterrows():
        raw_number = (
            str(row[col_product_no]).strip() if pd.notna(row[col_product_no]) else "0"
        )
        try:
            product_number = int(float(raw_number))
        except ValueError:
            product_number = 0

        product_name = (
            str(row[col_product_name]).strip()
            if pd.notna(row[col_product_name])
            else ""
        )
        script_content = (
            str(row[col_script]).strip() if pd.notna(row[col_script]) else ""
        )
        audio_code = str(row[col_audio]).strip() if pd.notna(row[col_audio]) else ""

        script_rows.append(
            ScriptRow(
                product_number=product_number,
                product_name=product_name,
                script_content=script_content,
                audio_code=audio_code,
                row_number=int(idx) + 2,
            )
        )

    logger.info(f"Total script rows: {len(script_rows)}")

    # Group by product_number, filter out product_number < 1
    from collections import defaultdict

    product_groups: dict[int, List[ScriptRow]] = defaultdict(list)
    for row in script_rows:
        if row.product_number >= 1:
            product_groups[row.product_number].append(row)
        else:
            logger.info(
                f"Skipping product #{row.product_number} "
                "(no sidebar card for product number < 1)"
            )

    products: List[ProductScript] = []
    for product_number in sorted(product_groups.keys()):
        rows = product_groups[product_number]
        products.append(
            ProductScript(
                product_number=product_number,
                product_name=rows[0].product_name,
                rows=rows,
            )
        )

    logger.info(f"Found {len(products)} unique products")
    return products


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
