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
import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional

import pandas as pd

from shared import (
    BrowserAutomation,
    setup_login,
    setup_logging,
    find_csv_file,
    load_csv,
    is_session_valid,
    get_session_file_path,
    CLICK_TIMEOUT,
    NAVIGATION_TIMEOUT,
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

SCRIPT_SELECTORS: dict[str, list[str]] = {
    "add_audio_button": [
        'button:has-text("Add Audio")',
        ':text("Add Audio")',
    ],
    "script_count": [
        "text=/\\d+\\/20/",
    ],
    "more_button": [
        'button[aria-label="more"]',
        'button:has([aria-label="more"])',
    ],
    "delete_menuitem": [
        '[role="menuitem"]:has-text("Delete")',
        'li:has-text("Delete")',
    ],
}

_SHARED_SCRIPT_HELPERS = (
    setup_login,
    setup_logging,
    find_csv_file,
    load_csv,
    is_session_valid,
)


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


class ScriptAutomation(BrowserAutomation):
    """Automates Set Live Content script management on live.app.anylive.jp."""

    SELECTORS = SCRIPT_SELECTORS

    def __init__(
        self,
        config: ScriptConfig,
        *,
        headless: bool = False,
        logger: logging.Logger,
        dry_run: bool = False,
        screenshots_dir: Optional[str] = None,
        browser_data_subdir: str = SCRIPT_BROWSER_DATA,
        session_filename: str = SCRIPT_SESSION_FILE,
    ) -> None:
        super().__init__(
            headless=headless,
            logger=logger,
            dry_run=dry_run,
            screenshots_dir=screenshots_dir,
            browser_data_subdir=browser_data_subdir,
            session_filename=session_filename,
            login_url=SCRIPT_LOGIN_URL,
            base_url=config.base_url,
        )
        self.config = config

    async def navigate_to_set_live_content(self) -> bool:
        """Navigate to the Set Live Content tab (default active tab)."""
        if self.page is None:
            raise RuntimeError("Browser page is not initialized")

        self.logger.info(f"Navigating to {self.config.base_url}")
        await self.page.goto(
            self.config.base_url,
            wait_until="domcontentloaded",
            timeout=NAVIGATION_TIMEOUT,
        )
        await asyncio.sleep(1.5)
        try:
            await self.page.wait_for_selector(
                ':text("Script Configuration"), :text("Live Products")',
                timeout=CLICK_TIMEOUT,
            )
            self.logger.info("On Set Live Content page")
            return True
        except Exception as e:
            self.logger.warning(f"Could not verify Set Live Content page: {e}")
            return True

    async def select_product(self, product_number: int) -> bool:
        """Click a product card in the left sidebar by its index number."""
        if self.page is None:
            raise RuntimeError("Browser page is not initialized")

        num_str = str(product_number)
        self.logger.debug(f"Selecting product #{product_number}")
        await self.page.evaluate(
            """() => {
                document.querySelectorAll('[data-script-product]').forEach(
                    el => el.removeAttribute('data-script-product')
                );
            }"""
        )

        found = await self.page.evaluate(
            """(targetNum) => {
                // Find sidebar product cards — each card has a number text element
                // The sidebar contains numbered cards (1-60), each with a clickable area
                const allDivs = document.querySelectorAll('div');
                for (const div of allDivs) {
                    // Look for elements that contain ONLY the target number as text
                    const walker = document.createTreeWalker(div, NodeFilter.SHOW_TEXT);
                    while (walker.nextNode()) {
                        const text = walker.currentNode.textContent.trim();
                        if (text !== targetNum) continue;
                        // Walk up to find a card-like container (has sibling with image)
                        let el = walker.currentNode.parentElement;
                        for (let i = 0; i < 5; i++) {
                            if (!el) break;
                            // Check if this element or its parent contains a product image
                            const hasImg = el.querySelector('img');
                            if (hasImg) {
                                el.setAttribute('data-script-product', targetNum);
                                return true;
                            }
                            el = el.parentElement;
                        }
                    }
                }
                return false;
            }""",
            num_str,
        )

        if not found:
            self.logger.warning(
                f"Could not find sidebar card for product #{product_number}"
            )
            return False

        locator = self.page.locator(f'[data-script-product="{num_str}"]')
        if await locator.count() == 0:
            self.logger.warning(f"Tagged element disappeared for #{product_number}")
            return False

        await locator.first.scroll_into_view_if_needed()
        await locator.first.click()
        await asyncio.sleep(1.5)
        self.logger.debug(f"Selected product #{product_number}")
        return True

    async def get_script_count(self) -> int:
        """Read the current script count from the 'N/20' text in center pane."""
        if self.page is None:
            raise RuntimeError("Browser page is not initialized")

        try:
            count_el = self.page.locator("text=/^\\d+\\/20$/")
            if await count_el.count() > 0:
                text = await count_el.first.text_content()
                if text:
                    return int(text.split("/")[0])
        except Exception as e:
            self.logger.debug(f"Could not read script count: {e}")
        return 0

    async def get_product_count(self) -> int:
        """Read total product count from sidebar header (e.g., '60/60' -> 60)."""
        if self.page is None:
            raise RuntimeError("Browser page is not initialized")

        try:
            count_el = self.page.locator("text=/^\\d+\\/\\d+$/")
            if await count_el.count() > 0:
                text = await count_el.first.text_content()
                if text:
                    return int(text.split("/")[0])
        except Exception as e:
            self.logger.debug(f"Could not read product count: {e}")
        return 60


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

    def _get_cell_value(row: pd.Series, key: str) -> Any:
        value = row.get(key, "")
        if isinstance(value, pd.Series):
            return value.iloc[0] if not value.empty else ""
        return value

    def _get_cell_text(row: pd.Series, key: str) -> str:
        value = _get_cell_value(row, key)
        return "" if pd.isna(value) else str(value).strip()

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
            df = pd.DataFrame(df.iloc[1:].reset_index(drop=True))
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
    df = pd.DataFrame(df[df[col_product_name] != col_product_name])

    # Forward-fill product_number and product_name
    df[col_product_name] = df[col_product_name].replace("", pd.NA)
    df[col_product_name] = df[col_product_name].ffill()
    df[col_product_no] = df[col_product_no].replace("", pd.NA)
    df[col_product_no] = df[col_product_no].ffill()

    # Filter rows that have either script_content or audio_code
    valid_rows = pd.DataFrame(df[df[col_script].notna() | df[col_audio].notna()])
    logger.info(f"Valid script rows: {len(valid_rows)}")

    script_rows: List[ScriptRow] = []
    for row_number, (_, row) in enumerate(valid_rows.iterrows(), start=2):
        raw_number = _get_cell_text(row, col_product_no) or "0"
        try:
            product_number = int(float(raw_number))
        except ValueError:
            product_number = 0

        product_name = _get_cell_text(row, col_product_name)
        script_content = _get_cell_text(row, col_script)
        audio_code = _get_cell_text(row, col_audio)

        script_rows.append(
            ScriptRow(
                product_number=product_number,
                product_name=product_name,
                script_content=script_content,
                audio_code=audio_code,
                row_number=row_number,
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
