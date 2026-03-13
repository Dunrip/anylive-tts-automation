#!/usr/bin/env python3
"""AnyLive Set Live Content Script Automation.

Automates script deletion and audio upload on the 'Set Live Content' tab
of live.app.anylive.jp. Supports --delete-scripts mode to remove all
existing scripts from every product, and upload mode (default) to add
audio files from CSV.
"""

import argparse
import json
import logging
import os
import asyncio
from dataclasses import dataclass, field
from datetime import datetime
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
    MAX_RETRIES,
    RETRY_DELAY_SECONDS,
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

    async def _wait_for_delete_confirmation(
        self, expected_count: int, timeout_s: float = 10.0
    ) -> bool:
        """Poll until script count drops to expected_count."""
        interval = 0.5
        elapsed = 0.0
        while elapsed < timeout_s:
            current = await self.get_script_count()
            if current == expected_count:
                return True
            await asyncio.sleep(interval)
            elapsed += interval
        return False

    async def _delete_single_script(
        self, product_number: int, current_count: int
    ) -> bool:
        """Delete the FIRST script row in the center pane.

        Always targets the first row because rows shift up after each deletion.
        Flow: click 'more' button -> wait for dropdown -> click 'Delete' menuitem.
        """
        if self.page is None:
            raise RuntimeError("Browser page is not initialized")

        try:
            more_btn = self.page.get_by_role("button", name="more", exact=True).first
            if await more_btn.count() == 0:
                more_btn = self.page.locator('[aria-label="more"]').first

            if await more_btn.count() == 0:
                self.logger.error(
                    f"Could not find 'more' button for product #{product_number}"
                )
                return False

            await more_btn.scroll_into_view_if_needed()
            await more_btn.click()
            await asyncio.sleep(0.3)

            delete_item = self.page.get_by_role("menuitem", name="Delete").first
            try:
                await delete_item.wait_for(state="visible", timeout=CLICK_TIMEOUT)
            except Exception:
                delete_item = self.page.locator(
                    '[role="menuitem"]:has-text("Delete")'
                ).first

            await delete_item.click()
            await asyncio.sleep(0.5)

            confirmed = await self._wait_for_delete_confirmation(current_count - 1)
            if not confirmed:
                self.logger.warning(
                    f"Delete confirmation timeout for product #{product_number} "
                    f"(expected count: {current_count - 1})"
                )
            return confirmed

        except Exception as e:
            self.logger.error(
                f"Error deleting script for product #{product_number}: {e}"
            )
            return False

    async def delete_product_scripts(
        self, product_number: int, dry_run: bool = False
    ) -> tuple[bool, int]:
        """Delete all scripts from a product. Returns (success, scripts_deleted)."""
        if not await self.select_product(product_number):
            return False, 0

        count = await self.get_script_count()

        if count == 0:
            self.logger.info(f"Product #{product_number} has no scripts to delete")
            return True, 0

        if dry_run:
            self.logger.info(
                f"DRY RUN: Would delete {count} scripts from product #{product_number}"
            )
            return True, 0

        deleted = 0
        while True:
            current_count = await self.get_script_count()
            if current_count == 0:
                break

            ok = False
            for attempt in range(MAX_RETRIES):
                ok = await self._delete_single_script(product_number, current_count)
                if ok:
                    break
                self.logger.warning(
                    f"Delete attempt {attempt + 1}/{MAX_RETRIES} failed for "
                    f"product #{product_number}, retrying..."
                )
                await asyncio.sleep(RETRY_DELAY_SECONDS)

            if not ok:
                self.logger.error(
                    f"Failed to delete script for product #{product_number} "
                    f"after {MAX_RETRIES} attempts, stopping after {deleted} deletions"
                )
                return False, deleted

            deleted += 1
            self.logger.debug(
                f"Deleted script {deleted} for product #{product_number} "
                f"({current_count - 1} remaining)"
            )

        self.logger.info(f"Product #{product_number}: deleted {deleted} scripts")
        return True, deleted

    async def delete_all_scripts(
        self,
        start_product: int = 1,
        limit: Optional[int] = None,
        dry_run: bool = False,
    ) -> list[dict]:
        """Delete all scripts from all products in the sidebar.

        Does NOT require CSV - iterates products from sidebar UI.
        Returns list of result dicts for report generation.
        """
        total = await self.get_product_count()
        end_product = min(start_product + limit, total + 1) if limit else total + 1

        results: list[dict] = []
        for product_number in range(start_product, end_product):
            try:
                success, deleted = await self.delete_product_scripts(
                    product_number, dry_run=dry_run
                )
                if not success:
                    try:
                        await self.take_screenshot(f"product_{product_number}")
                    except Exception as screenshot_err:
                        self.logger.debug(f"Screenshot failed: {screenshot_err}")
                results.append(
                    {
                        "product_number": product_number,
                        "scripts_deleted": deleted,
                        "success": success,
                        "error": None if success else "Failed to delete all scripts",
                    }
                )
            except Exception as e:
                error_msg = str(e)
                self.logger.error(
                    f"Error processing product #{product_number}: {error_msg}"
                )
                try:
                    await self.take_screenshot(f"product_{product_number}")
                except Exception as screenshot_err:
                    self.logger.debug(f"Screenshot failed: {screenshot_err}")
                results.append(
                    {
                        "product_number": product_number,
                        "scripts_deleted": 0,
                        "success": False,
                        "error": error_msg,
                    }
                )

        return results

    async def _wait_for_upload_confirmation_by_count(
        self, expected_count: int, timeout_s: float = 20.0
    ) -> bool:
        """Poll until script count increments to expected_count."""
        interval = 0.5
        elapsed = 0.0
        while elapsed < timeout_s:
            current = await self.get_script_count()
            if current == expected_count:
                return True
            await asyncio.sleep(interval)
            elapsed += interval
        return False

    async def _upload_audio_file(self, audio_path: str) -> bool:
        """Upload a single audio file via the 'Add Audio' button.

        Uses Playwright's expect_file_chooser() to handle the native file dialog.
        Polls for script count to increment as upload confirmation.
        """
        if self.page is None:
            raise RuntimeError("Browser page is not initialized")

        count_before = await self.get_script_count()

        try:
            add_btn = self.page.get_by_role("button", name="Add Audio")
            if await add_btn.count() == 0:
                add_btn = self.page.locator('button:has-text("Add Audio")')

            if await add_btn.count() == 0:
                self.logger.error("Could not find 'Add Audio' button")
                return False

            async with self.page.expect_file_chooser(timeout=CLICK_TIMEOUT) as fc_info:
                await add_btn.first.click()
            file_chooser = await fc_info.value
            await file_chooser.set_files(audio_path)

            audio_filename = os.path.basename(audio_path)
            self.logger.debug(
                f"File set: {audio_filename}, waiting for OSS upload confirmation..."
            )

            confirmed = await self._wait_for_upload_confirmation_by_count(
                count_before + 1, timeout_s=20.0
            )
            if confirmed:
                self.logger.info(f"Uploaded: {audio_filename}")
            else:
                self.logger.warning(
                    f"Upload confirmation timeout for {audio_filename} "
                    f"(expected count: {count_before + 1})"
                )
            return confirmed

        except Exception as e:
            self.logger.error(f"Error uploading {os.path.basename(audio_path)}: {e}")
            return False

    async def upload_product_scripts(
        self, product: ProductScript, dry_run: bool = False
    ) -> bool:
        """Upload audio files for all rows in a product."""
        if not await self.select_product(product.product_number):
            product.error = f"Could not select product #{product.product_number}"
            return False

        current_count = await self.get_script_count()
        rows_to_upload = len(product.rows)

        if current_count + rows_to_upload > 20:
            product.error = (
                f"Upload would exceed 20 scripts for product #{product.product_number} "
                f"(current: {current_count}, adding: {rows_to_upload})"
            )
            self.logger.error(product.error)
            return False

        if dry_run:
            for row in product.rows:
                audio_path = resolve_audio_file(
                    row.audio_code,
                    row.product_number,
                    self.config.audio_dir,
                    self.config.audio_extensions,
                    self.logger,
                )
                if audio_path:
                    self.logger.info(
                        f"DRY RUN: Would upload {os.path.basename(audio_path)} "
                        f"for product #{product.product_number}"
                    )
                else:
                    self.logger.warning(
                        f"DRY RUN: Audio not found for code '{row.audio_code}' "
                        f"(product #{product.product_number})"
                    )
            product.success = True
            return True

        uploaded = 0
        for i, row in enumerate(product.rows):
            audio_path = resolve_audio_file(
                row.audio_code,
                row.product_number,
                self.config.audio_dir,
                self.config.audio_extensions,
                self.logger,
            )
            if not audio_path:
                self.logger.warning(
                    f"Skipping row {i + 1}: audio not found for code '{row.audio_code}'"
                )
                continue

            ok = await self._upload_audio_file(audio_path)
            if ok:
                uploaded += 1
                self.logger.info(
                    f"Uploaded {uploaded}/{rows_to_upload} audio for "
                    f"product #{product.product_number}: {os.path.basename(audio_path)}"
                )
            else:
                self.logger.warning(
                    f"Failed to upload row {i + 1} for product #{product.product_number}"
                )

        product.success = uploaded == rows_to_upload
        if not product.success:
            product.error = (
                f"{rows_to_upload - uploaded}/{rows_to_upload} uploads failed"
            )
        return product.success

    async def upload_all_scripts(
        self, products: List[ProductScript], dry_run: bool = False
    ) -> None:
        """Upload audio scripts for all products."""
        for product in products:
            try:
                await self.upload_product_scripts(product, dry_run=dry_run)
                if not product.success:
                    try:
                        await self.take_screenshot(f"product_{product.product_number}")
                    except Exception as screenshot_err:
                        self.logger.debug(f"Screenshot failed: {screenshot_err}")
            except Exception as e:
                product.error = str(e)
                product.success = False
                self.logger.error(
                    f"Error processing product #{product.product_number}: {e}"
                )
                try:
                    await self.take_screenshot(f"product_{product.product_number}")
                except Exception as screenshot_err:
                    self.logger.debug(f"Screenshot failed: {screenshot_err}")


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


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------
def generate_script_report(
    products: List[ProductScript],
    config: ScriptConfig,
    timestamp: str,
    logger: logging.Logger,
    mode: str = "upload",
    delete_results: Optional[list] = None,
    logs_dir: Optional[str] = None,
) -> dict:
    """Generate and save a JSON execution report."""
    if mode == "delete" and delete_results is not None:
        successful = sum(1 for r in delete_results if r["success"])
        failed = len(delete_results) - successful
        report = {
            "timestamp": datetime.now().isoformat(),
            "mode": "delete",
            "total_products": len(delete_results),
            "successful": successful,
            "failed": failed,
            "products": delete_results,
        }
        logger.info("")
        logger.info("=" * 70)
        logger.info("FINAL SCRIPT REPORT (DELETE MODE)")
        logger.info("=" * 70)
        logger.info(
            f"Total: {len(delete_results)} | Success: {successful} | Failed: {failed}"
        )
        for r in delete_results:
            status = "OK" if r["success"] else "FAILED"
            logger.info(
                f"  {status} Product #{r['product_number']}: "
                f"{r['scripts_deleted']} scripts deleted"
            )
            if r.get("error"):
                logger.info(f"      Error: {r['error']}")
    else:
        successful = sum(1 for p in products if p.success)
        failed = len(products) - successful
        report = {
            "timestamp": datetime.now().isoformat(),
            "mode": "upload",
            "total_products": len(products),
            "successful": successful,
            "failed": failed,
            "products": [
                {
                    "product_number": p.product_number,
                    "product_name": p.product_name,
                    "scripts": len(p.rows),
                    "success": p.success,
                    "error": p.error,
                }
                for p in products
            ],
        }
        logger.info("")
        logger.info("=" * 70)
        logger.info("FINAL SCRIPT REPORT (UPLOAD MODE)")
        logger.info("=" * 70)
        logger.info(
            f"Total: {len(products)} | Success: {successful} | Failed: {failed}"
        )
        for p in products:
            status = "OK" if p.success else "FAILED"
            logger.info(
                f"  {status} Product #{p.product_number} ({p.product_name}): "
                f"{len(p.rows)} scripts"
            )
            if p.error:
                logger.info(f"      Error: {p.error}")

    logs_path = Path(logs_dir) if logs_dir else Path("logs")
    logs_path.mkdir(exist_ok=True)
    report_path = logs_path / f"script_report_{timestamp}.json"

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    logger.info(f"Report saved: {report_path}")
    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
async def main() -> None:
    parser = argparse.ArgumentParser(
        description="AnyLive Script Automation (Set Live Content)"
    )
    parser.add_argument("--setup", action="store_true", help="One-time login setup")
    parser.add_argument(
        "--csv", type=str, help="Path to CSV file (auto-detects if not specified)"
    )
    parser.add_argument(
        "--client",
        type=str,
        help="Client name (loads configs/{NAME}_script.json)",
    )
    parser.add_argument("--config", type=str, help="Path to script config JSON file")
    parser.add_argument(
        "--delete-scripts",
        action="store_true",
        help="Delete all scripts from all products (CSV not required)",
    )
    parser.add_argument(
        "--start-product",
        type=int,
        default=1,
        help="Starting product number (default: 1)",
    )
    parser.add_argument("--limit", type=int, help="Limit number of products to process")
    parser.add_argument(
        "--headless", action="store_true", help="Run browser in headless mode"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview actions without browser interaction",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Keep browser open after execution for debugging",
    )
    parser.add_argument("--base-url", type=str, help="Override base URL from config")
    parser.add_argument("--audio-dir", type=str, help="Override audio directory path")

    args = parser.parse_args()

    # Resolve client and session paths
    _client: Optional[str] = args.client
    _session_filename, _browser_data_subdir = _get_script_session_paths(_client)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    logger = setup_logging(
        timestamp, logger_name="auto_script", log_prefix="auto_script"
    )

    logger.info("ANYLIVE SCRIPT AUTOMATION (SET LIVE CONTENT)")
    logger.info("=" * 70)

    if _client:
        logger.info(f"Using account: {_client}")

    if args.setup:
        await setup_login(
            logger,
            login_url=SCRIPT_LOGIN_URL,
            browser_data_subdir=_browser_data_subdir,
            session_filename=_session_filename,
        )
        return

    if not is_session_valid(_session_filename):
        logger.error("No session found. Please run with --setup first.")
        logger.info(
            f"   python auto_script.py --setup --client {_client or '<client_name>'}"
        )
        return

    if _client:
        _save_last_script_client(_client)

    # Resolve config path
    config_path: Optional[str] = None
    if args.client:
        config_path = f"configs/{args.client}_script.json"
    elif args.config:
        config_path = args.config

    cli_overrides: dict = {}
    if args.base_url:
        cli_overrides["base_url"] = args.base_url
    if args.audio_dir:
        cli_overrides["audio_dir"] = args.audio_dir

    # For delete mode with only --base-url, create a minimal config
    if config_path is None and args.delete_scripts and args.base_url:
        config = ScriptConfig(base_url=args.base_url)
    elif config_path is None and not args.delete_scripts:
        logger.error("Please specify --client or --config for upload mode")
        logger.info("   python auto_script.py --client mahajak --csv scripts.csv")
        return
    elif config_path is None:
        logger.error("Please specify --client or --config")
        return
    else:
        try:
            config = load_script_config(
                config_path, cli_overrides if cli_overrides else None
            )
            logger.info(f"Loaded config: {config_path}")
        except FileNotFoundError as e:
            logger.error(f"{e}")
            return
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return

    automation = ScriptAutomation(
        config=config,
        headless=args.headless,
        logger=logger,
        dry_run=args.dry_run,
        browser_data_subdir=_browser_data_subdir,
        session_filename=_session_filename,
    )

    try:
        await automation.start_browser()

        if not await automation.navigate_to_set_live_content():
            logger.error("Failed to navigate to Set Live Content page")
            return

        if args.delete_scripts:
            # Delete mode: CSV not required, iterate products from sidebar
            logger.info(
                f"DELETE MODE: Deleting scripts from products "
                f"starting at #{args.start_product}"
            )
            if args.dry_run:
                logger.info("DRY RUN MODE: No scripts will be deleted")

            delete_results = await automation.delete_all_scripts(
                start_product=args.start_product,
                limit=args.limit,
                dry_run=args.dry_run,
            )
            generate_script_report(
                products=[],
                config=config,
                timestamp=timestamp,
                logger=logger,
                mode="delete",
                delete_results=delete_results,
            )

        else:
            # Upload mode: CSV required
            if args.dry_run:
                logger.info("DRY RUN MODE: No audio will be uploaded")

            try:
                csv_from_config = getattr(config, "csv", None)
                csv_path = find_csv_file(args.csv or csv_from_config or None)
            except (FileNotFoundError, ValueError) as e:
                logger.error(f"{e}")
                return

            df = load_csv(csv_path, logger)
            products = parse_script_csv(df, config, logger)

            if not products:
                logger.error("No products to process")
                return

            # Apply start-product filter
            if args.start_product > 1:
                products = [
                    p for p in products if p.product_number >= args.start_product
                ]
                logger.info(f"Starting from product #{args.start_product}")

            if args.limit:
                products = products[: args.limit]
                logger.info(f"Limited to {args.limit} products")

            await automation.upload_all_scripts(products, dry_run=args.dry_run)

            generate_script_report(
                products=products,
                config=config,
                timestamp=timestamp,
                logger=logger,
                mode="upload",
            )

    finally:
        if args.debug:
            logger.info("")
            logger.info("=" * 70)
            logger.info("DEBUG MODE: Browser is open for inspection.")
            logger.info("   Press Enter to close the browser and exit.")
            logger.info("=" * 70)
            input()
        await automation.close()


if __name__ == "__main__":
    asyncio.run(main())
