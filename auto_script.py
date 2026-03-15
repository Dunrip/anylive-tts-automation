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
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional

import pandas as pd

from shared import (
    BrowserAutomation,
    async_debug_pause,
    ensure_client_config,
    get_live_session_paths,
    save_last_client,
    setup_login,
    setup_logging,
    find_csv_file,
    load_csv,
    load_jsonc,
    is_session_valid,
    CLICK_TIMEOUT,
    LIVE_BROWSER_DATA,
    LIVE_LOGIN_URL,
    LIVE_SESSION_FILE,
    MAX_RETRIES,
    NAVIGATION_TIMEOUT,
    RETRY_DELAY_SECONDS,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SCRIPT_LAST_CLIENT_FILE = "state/script_last_client.json"

SCRIPT_SELECTORS: dict[str, list[str]] = {
    "add_audio_button": [
        'button:has-text("Upload Audio Script")',
        'button:has-text("Add Audio")',
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
    "script_row_name": [
        '[aria-label="more"]',  # Each script row has a "more" button — used as anchor to find row text
    ],
}


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
    scripts_skipped: int = 0


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
        debug: bool = False,
        screenshots_dir: Optional[str] = None,
        browser_data_subdir: str = LIVE_BROWSER_DATA,
        session_filename: str = LIVE_SESSION_FILE,
    ) -> None:
        super().__init__(
            headless=headless,
            logger=logger,
            dry_run=dry_run,
            debug=debug,
            screenshots_dir=screenshots_dir,
            browser_data_subdir=browser_data_subdir,
            session_filename=session_filename,
            login_url=LIVE_LOGIN_URL,
            base_url=config.base_url,
        )
        self.config = config

    def _log_product_header(
        self, index: int, total: int, product_number: int, label: str
    ) -> None:
        self.logger.info("")
        self.logger.info("=" * 60)
        self.logger.info(f" [{index}/{total}] Product #{product_number} — {label}")
        self.logger.info("-" * 60)

    def _log_product_result(self, status: str, detail: str) -> None:
        self.logger.info(f"  → {status}: {detail}")

    async def navigate_to_set_live_content(self) -> bool:
        """Navigate to the Set Live Content tab (default active tab)."""
        if self.page is None:
            raise RuntimeError("Browser page is not initialized")

        current = self.page.url
        target = self.config.base_url.rstrip("/")
        if not current.rstrip("/").startswith(target):
            self.logger.info(f"Navigating to {self.config.base_url}")
            await self.page.goto(
                self.config.base_url,
                wait_until="domcontentloaded",
                timeout=NAVIGATION_TIMEOUT,
            )
            await asyncio.sleep(1.5)
        else:
            self.logger.info("Already on Set Live Content page, skipping reload")

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
                // Scope search to product card rows only: find all
                // .product-card elements, walk to each card's parent row,
                // and check if that row contains the target product number.
                const cards = document.querySelectorAll('.product-card');
                for (const card of cards) {
                    const row = card.parentElement;
                    if (!row) continue;
                    const walker = document.createTreeWalker(
                        row, NodeFilter.SHOW_TEXT
                    );
                    while (walker.nextNode()) {
                        const text = walker.currentNode.textContent.trim();
                        if (text !== targetNum) continue;

                        let isCounter = false;
                        let check = walker.currentNode.parentElement;
                        for (let c = 0; c < 3 && check; c++) {
                            if (/^\\d+\\s*\\/\\s*\\d+$/.test(
                                check.textContent.trim()
                            )) { isCounter = true; break; }
                            check = check.parentElement;
                        }
                        if (isCounter) continue;

                        row.setAttribute('data-script-product', targetNum);
                        return true;
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

        # networkidle waits for SPA data fetch to complete before reading script count
        try:
            await self.page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            await asyncio.sleep(1.5)
        await asyncio.sleep(0.5)

        self.logger.debug(f"Selected product #{product_number}")
        return True

    async def get_script_count(self) -> int:
        """Read the current script count from the 'N/20' text in center pane."""
        if self.page is None:
            raise RuntimeError("Browser page is not initialized")

        try:
            count_el = self.page.locator("text=/^\\d+\\/20$/")
            matches = await count_el.count()
            if matches > 0:
                text = await count_el.first.text_content()
                if text:
                    value = int(text.split("/")[0])
                    self.logger.debug(f"Script count: {text} ({matches} matches)")
                    return value
            self.logger.debug("Script count selector matched 0 elements")
        except Exception as e:
            self.logger.debug(f"Could not read script count: {e}")
        return 0

    async def get_existing_script_names(self) -> list[str]:
        """Read all script filenames from the center pane.

        Uses the 'more' button (present on each script row) as an anchor,
        then walks up to the nearest row container to extract the filename.
        Returns raw displayed names (not normalized).
        On failure, returns an empty list as a safe fallback.
        """
        if self.page is None:
            raise RuntimeError("Browser page is not initialized")

        try:
            names: list[str] = await self.page.evaluate(
                """() => {
                    const buttons = document.querySelectorAll('[aria-label="more"]');
                    const results = [];
                    for (const btn of buttons) {
                        let found = false;
                        let el = btn.parentElement;
                        // Walk up at most 5 levels to find the script row
                        for (let i = 0; i < 5 && el && !found; i++) {
                            const texts = el.querySelectorAll('span, p');
                            for (const t of texts) {
                                // Only check direct text (avoid nested duplicates)
                                if (t.children.length > 0) continue;
                                const txt = t.textContent?.trim();
                                if (txt
                                    && txt !== 'more'
                                    && !txt.includes('/')
                                    && txt.length > 2
                                    && txt.length < 100
                                    && /\\.[a-zA-Z0-9]{2,4}$/.test(txt)) {
                                    results.push(txt);
                                    found = true;
                                    break;
                                }
                            }
                            el = el.parentElement;
                        }
                    }
                    return [...new Set(results)];
                }"""
            )
            if names:
                self.logger.debug(f"Found {len(names)} existing scripts: {names}")
            else:
                self.logger.debug("No existing script names found in center pane")
            return names
        except Exception as e:
            self.logger.warning(f"Could not read existing script names: {e}")
            return []

    async def scan_sidebar_script_status(self) -> dict[int, int]:
        """Pre-scan all sidebar product cards for script labels.

        Reads the visible 'No product script' / 'N product scripts' tag on
        each card WITHOUT clicking into the product.  Returns a mapping of
        ``{product_number: script_count}`` for products that have at least
        one script.  Products with 'No product script' are omitted.
        """
        if self.page is None:
            raise RuntimeError("Browser page is not initialized")

        raw: dict[str, int] = await self.page.evaluate(
            """() => {
                const labels = document.querySelectorAll('p');
                const result = {};
                for (const label of labels) {
                    const text = label.textContent?.trim();
                    if (!text) continue;
                    const m = text.match(/^(\\d+) product scripts?$/);
                    if (!m) continue;
                    const count = parseInt(m[1], 10);
                    if (count === 0) continue;

                    // Walk up past the product-card to its parent row,
                    // which contains the product number as a child element.
                    let row = label.parentElement;
                    for (let i = 0; i < 10 && row; i++) {
                        if (row.classList?.contains('product-card')) {
                            row = row.parentElement;
                            continue;
                        }
                        if (!row.querySelector('.product-card')) {
                            row = row.parentElement;
                            continue;
                        }
                        // Found the row that contains a product-card child.
                        const walker = document.createTreeWalker(
                            row, NodeFilter.SHOW_TEXT
                        );
                        while (walker.nextNode()) {
                            const t = walker.currentNode.textContent.trim();
                            if (!/^\\d{1,3}$/.test(t)) continue;
                            const num = parseInt(t, 10);
                            let isCounter = false;
                            let chk = walker.currentNode.parentElement;
                            for (let c = 0; c < 3 && chk; c++) {
                                if (/^\\d+\\s*\\/\\s*\\d+$/.test(
                                    chk.textContent.trim()
                                )) { isCounter = true; break; }
                                chk = chk.parentElement;
                            }
                            if (!isCounter && num >= 1) {
                                result[String(num)] = count;
                                break;
                            }
                        }
                        break;
                    }
                }
                return result;
            }"""
        )

        products_with_scripts: dict[int, int] = {int(k): v for k, v in raw.items()}
        if products_with_scripts:
            self.logger.info(
                f"Pre-scan: {len(products_with_scripts)} products have scripts "
                f"({', '.join(f'#{n}({c})' for n, c in sorted(products_with_scripts.items()))})"
            )
        else:
            self.logger.info("Pre-scan: no products have scripts")
        return products_with_scripts

    async def get_product_count(self) -> int:
        """Read total product count from sidebar header (e.g., '60/60' -> 60).

        Excludes N/20 matches (script counter) by checking denominator != 20.
        """
        if self.page is None:
            raise RuntimeError("Browser page is not initialized")

        try:
            count_el = self.page.locator("text=/^\\d+\\/\\d+$/")
            for i in range(await count_el.count()):
                text = await count_el.nth(i).text_content()
                if not text:
                    continue
                parts = text.split("/")
                if len(parts) == 2 and parts[1].strip() != "20":
                    return int(parts[0])
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

    async def _dismiss_open_menus(self) -> None:
        """Press Escape to close any lingering dropdown/context menu."""
        if self.page is None:
            return
        try:
            await self.page.keyboard.press("Escape")
            await asyncio.sleep(0.2)
        except Exception:
            pass

    async def _delete_single_script(
        self, product_number: int, current_count: int
    ) -> bool:
        """Delete the FIRST script row in the center pane.

        Always targets the first row because rows shift up after each deletion.
        Flow: dismiss stale menus -> click 'more' -> click 'Delete' menuitem.
        """
        if self.page is None:
            raise RuntimeError("Browser page is not initialized")

        try:
            await self._dismiss_open_menus()

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
            await asyncio.sleep(0.5)

            delete_item = self.page.get_by_role("menuitem", name="Delete").first
            try:
                await delete_item.wait_for(state="visible", timeout=CLICK_TIMEOUT)
            except Exception:
                delete_item = self.page.locator(
                    '[role="menuitem"]:has-text("Delete")'
                ).first

            await delete_item.click()
            await asyncio.sleep(0.8)

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
            # Fallback: poll briefly in case center pane is still loading.
            # The sidebar pre-scan already filtered empty products, so this
            # only fires when scripts genuinely need time to render.
            poll_timeout = 10.0
            poll_interval = 0.5
            elapsed = 0.0
            while elapsed < poll_timeout:
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval
                count = await self.get_script_count()
                if count > 0:
                    break

        if count == 0:
            self.logger.info("  No scripts to delete")
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
                if attempt > 0:
                    await self._dismiss_open_menus()
                    await asyncio.sleep(RETRY_DELAY_SECONDS)
                    current_count = await self.get_script_count()
                    if current_count == 0:
                        break
                ok = await self._delete_single_script(product_number, current_count)
                if ok:
                    break
                self.logger.warning(
                    f"Delete attempt {attempt + 1}/{MAX_RETRIES} failed for "
                    f"product #{product_number}, retrying..."
                )

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
        all_product_numbers = list(range(start_product, end_product))

        script_status = await self.scan_sidebar_script_status()
        products_with_scripts = [n for n in all_product_numbers if n in script_status]
        products_without_scripts = [
            n for n in all_product_numbers if n not in script_status
        ]

        if products_without_scripts:
            self.logger.info(f"Skipping {len(products_without_scripts)} empty products")

        results: list[dict] = []
        for product_number in products_without_scripts:
            results.append(
                {
                    "product_number": product_number,
                    "scripts_deleted": 0,
                    "success": True,
                    "error": None,
                }
            )

        total_to_delete = len(products_with_scripts)
        if total_to_delete == 0:
            self.logger.info("No products have scripts — nothing to delete")
            return sorted(results, key=lambda r: r["product_number"])

        for idx, product_number in enumerate(products_with_scripts, 1):
            expected = script_status.get(product_number, 0)
            self._log_product_header(
                idx, total_to_delete, product_number, "Deleting scripts"
            )
            try:
                success, deleted = await self.delete_product_scripts(
                    product_number, dry_run=dry_run
                )

                if success and deleted == 0 and expected > 0 and not dry_run:
                    self.logger.warning(
                        f"  Pre-scan expected {expected} scripts but center "
                        f"pane showed 0 — re-selecting product #{product_number}"
                    )
                    success, deleted = await self.delete_product_scripts(
                        product_number, dry_run=dry_run
                    )

                if success:
                    suffix = "(dry run)" if dry_run else "deleted"
                    self._log_product_result("OK", f"{deleted} scripts {suffix}")
                else:
                    self._log_product_result(
                        "FAILED", f"Stopped after {deleted} deletions"
                    )
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
                self._log_product_result("ERROR", error_msg)
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

        return sorted(results, key=lambda r: r["product_number"])

    async def _wait_for_upload_confirmation_by_count(
        self, expected_count: int, timeout_s: float = 20.0
    ) -> bool:
        """Poll until script count reaches at least expected_count."""
        interval = 0.5
        elapsed = 0.0
        while elapsed < timeout_s:
            current = await self.get_script_count()
            if current >= expected_count:
                return True
            await asyncio.sleep(interval)
            elapsed += interval
        return False

    async def _is_button_ready(self, btn: Any) -> bool:
        """Check that a button locator is visible and enabled (not loading)."""
        try:
            return (
                await btn.count() > 0
                and await btn.first.is_visible()
                and await btn.first.is_enabled()
            )
        except Exception:
            return False

    async def _wait_for_upload_button(
        self, timeout_s: float = 30.0, interval: float = 0.5
    ) -> Optional[Any]:
        """Wait for upload button to become visible and enabled.

        The Script Configuration panel shows a loading spinner after selecting
        a product.  The 'Upload Audio Script' / 'Add Audio' button renders
        as disabled with data-loading while the spinner runs.  Polling until
        enabled avoids clicking a disabled button.

        Returns the Playwright Locator for the button, or None on timeout.
        """
        if self.page is None:
            raise RuntimeError("Browser page is not initialized")

        selectors_role = [
            ("Upload Audio Script", None),
            ("Add Audio", None),
        ]
        selectors_css = SCRIPT_SELECTORS["add_audio_button"]

        elapsed = 0.0
        while elapsed < timeout_s:
            for name, _ in selectors_role:
                btn = self.page.get_by_role("button", name=name)
                if await self._is_button_ready(btn):
                    return btn
            for sel in selectors_css:
                btn = self.page.locator(sel)
                if await self._is_button_ready(btn):
                    return btn

            await asyncio.sleep(interval)
            elapsed += interval

        self.logger.error(
            "Upload button not ready (still disabled/loading) "
            f"after waiting {timeout_s}s"
        )
        return None

    async def _upload_audio_file(self, audio_path: str) -> bool:
        """Upload a single audio file via the 'Add Audio' button.

        Uses Playwright's expect_file_chooser() to handle the native file dialog.
        Polls for script count to increment as upload confirmation.
        """
        if self.page is None:
            raise RuntimeError("Browser page is not initialized")

        count_before = await self.get_script_count()

        try:
            add_btn = await self._wait_for_upload_button()
            if add_btn is None:
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
                count_before + 1, timeout_s=30.0
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
        self,
        product: ProductScript,
        dry_run: bool = False,
        sidebar_count: int = 0,
    ) -> bool:
        """Upload audio files for all rows in a product, skipping already-present scripts."""
        if not await self.select_product(product.product_number):
            product.error = f"Could not select product #{product.product_number}"
            return False

        current_count = await self.get_script_count()

        # Poll for center pane to load when sidebar indicates scripts exist
        # but the center pane hasn't rendered them yet (stale 0/20 read).
        if current_count == 0 and sidebar_count > 0:
            self.logger.debug(
                f"Script count is 0 but sidebar shows {sidebar_count} — "
                "polling for center pane to load..."
            )
            poll_timeout = 10.0
            poll_interval = 0.5
            elapsed = 0.0
            while elapsed < poll_timeout:
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval
                current_count = await self.get_script_count()
                if current_count > 0:
                    break
            if current_count == 0:
                self.logger.warning(
                    f"Center pane still shows 0 after {poll_timeout}s "
                    f"(sidebar expected {sidebar_count}) — proceeding cautiously"
                )

        # --- Detect existing scripts and filter ---
        try:
            existing_names = await self.get_existing_script_names()
        except Exception as e:
            self.logger.warning(f"Failed to read existing scripts: {e}")
            existing_names = []

        if current_count > 0 and not existing_names:
            self.logger.debug(
                f"Script count is {current_count} but no names found — retrying after 1s"
            )
            await asyncio.sleep(1.0)
            try:
                existing_names = await self.get_existing_script_names()
            except Exception as e:
                self.logger.warning(f"Retry failed to read existing scripts: {e}")
                existing_names = []

        existing_normalized = {_normalize_script_name(n) for n in existing_names}

        # Resolve audio paths and determine which rows need uploading
        rows_with_paths: list[tuple[ScriptRow, str]] = []
        skipped_rows: list[ScriptRow] = []
        missing_audio: list[ScriptRow] = []

        for row in product.rows:
            audio_path = resolve_audio_file(
                row.audio_code,
                row.product_number,
                self.config.audio_dir,
                self.config.audio_extensions,
                self.logger,
            )
            if not audio_path:
                missing_audio.append(row)
                continue

            filename = os.path.basename(audio_path)
            if _normalize_script_name(filename) in existing_normalized:
                skipped_rows.append(row)
                self.logger.info(
                    f"  Skipping '{filename}': already present on product #{product.product_number}"
                )
            else:
                rows_with_paths.append((row, audio_path))

        rows_to_upload = len(rows_with_paths)
        skipped_count = len(skipped_rows)
        total_rows = len(product.rows)
        product.scripts_skipped = skipped_count

        # Log summary
        if skipped_count > 0:
            self.logger.info(
                f"  Product #{product.product_number}: {rows_to_upload}/{total_rows} scripts "
                f"to upload ({skipped_count} already present)"
            )

        if rows_to_upload == 0 and skipped_count > 0:
            self.logger.info(
                f"  All {total_rows} scripts already present on product #{product.product_number}"
            )
            product.success = True
            return True

        # Overflow check with FILTERED count
        if current_count + rows_to_upload > 20:
            product.error = (
                f"Upload would exceed 20 scripts for product #{product.product_number} "
                f"(current: {current_count}, adding: {rows_to_upload})"
            )
            self.logger.error(product.error)
            return False

        if dry_run:
            for _row, audio_path in rows_with_paths:
                self.logger.info(f"  Would upload {os.path.basename(audio_path)}")
            for row in missing_audio:
                self.logger.warning(f"  Audio not found for code '{row.audio_code}'")
            product.success = True
            return True

        # Upload only filtered rows
        uploaded = 0
        timed_out = 0
        for _i, (row, audio_path) in enumerate(rows_with_paths):
            ok = await self._upload_audio_file(audio_path)
            if ok:
                uploaded += 1
            else:
                timed_out += 1
                self.logger.warning(
                    f"Failed to upload {os.path.basename(audio_path)} "
                    f"for product #{product.product_number}"
                )

        # --- Post-upload re-verification ---
        # When uploads succeed on the server but the UI counter is slow to
        # update, _upload_audio_file returns False (confirmation timeout).
        # Re-read the actual count to detect and correct these false negatives.
        if timed_out > 0 and uploaded < rows_to_upload:
            await asyncio.sleep(2.0)
            final_count = await self.get_script_count()
            expected_final = current_count + rows_to_upload
            if final_count >= expected_final:
                self.logger.info(
                    f"  Re-verification: count is {final_count}/20 "
                    f"(expected {expected_final}) — all uploads actually succeeded"
                )
                uploaded = rows_to_upload
            elif final_count > current_count + uploaded:
                recovered = final_count - current_count - uploaded
                self.logger.info(
                    f"  Re-verification: count is {final_count}/20 — "
                    f"recovered {recovered} upload(s) that timed out on confirmation"
                )
                uploaded += recovered

        product.success = uploaded == rows_to_upload
        if not product.success:
            product.error = (
                f"{rows_to_upload - uploaded}/{rows_to_upload} uploads failed"
            )
        return product.success

    def _is_page_alive(self) -> bool:
        """Check if the browser page is still usable."""
        if self.page is None:
            return False
        try:
            return not self.page.is_closed()
        except Exception:
            return False

    async def _refresh_page(self) -> bool:
        """Reload the page to reset SPA state (fixes stuck loading spinners)."""
        if self.page is None:
            return False
        try:
            self.logger.info("  Refreshing page to reset SPA state...")
            await self.page.reload(
                wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT
            )
            await asyncio.sleep(2.0)
            return True
        except Exception as e:
            self.logger.error(f"Page refresh failed: {e}")
            return False

    def _reset_product_state(self, product: ProductScript) -> None:
        """Reset a product's tracking fields for retry."""
        product.success = False
        product.error = None
        product.scripts_skipped = 0

    def _log_product_success(self, product: ProductScript, dry_run: bool) -> None:
        suffix = "(dry run)" if dry_run else "uploaded"
        if product.scripts_skipped > 0:
            self._log_product_result(
                "OK",
                f"{len(product.rows) - product.scripts_skipped}/{len(product.rows)} "
                f"scripts {suffix} ({product.scripts_skipped} already present)",
            )
        else:
            self._log_product_result("OK", f"{len(product.rows)} scripts {suffix}")

    async def upload_all_scripts(
        self, products: List[ProductScript], dry_run: bool = False
    ) -> None:
        """Upload audio scripts for all products."""
        total = len(products)
        refresh_every = 10
        products_since_refresh = 0

        script_status = await self.scan_sidebar_script_status()

        for idx, product in enumerate(products, 1):
            if not self._is_page_alive():
                self.logger.error(
                    "Browser page is closed — aborting remaining "
                    f"{total - idx + 1} product(s)"
                )
                for remaining in products[idx - 1 :]:
                    remaining.success = False
                    remaining.error = "Aborted: browser page closed"
                break

            if products_since_refresh >= refresh_every:
                self.logger.info(
                    f"Preventive page refresh after {products_since_refresh} products"
                )
                await self._refresh_page()
                products_since_refresh = 0

            self._log_product_header(
                idx,
                total,
                product.product_number,
                f"{product.product_name} ({len(product.rows)} scripts)",
            )
            try:
                sb_count = script_status.get(product.product_number, 0)
                await self.upload_product_scripts(
                    product,
                    dry_run=dry_run,
                    sidebar_count=sb_count,
                )

                if not product.success and not dry_run:
                    self.logger.info(
                        f"  Retrying product #{product.product_number} after page refresh..."
                    )
                    if await self._refresh_page():
                        self._reset_product_state(product)
                        await self.upload_product_scripts(
                            product,
                            dry_run=dry_run,
                            sidebar_count=sb_count,
                        )
                        products_since_refresh = 0

                if product.success:
                    self._log_product_success(product, dry_run)
                else:
                    self._log_product_result("FAILED", product.error or "Unknown error")
                    try:
                        await self.take_screenshot(f"product_{product.product_number}")
                    except Exception as screenshot_err:
                        self.logger.debug(f"Screenshot failed: {screenshot_err}")
            except Exception as e:
                product.error = str(e)
                product.success = False
                self._log_product_result("ERROR", str(e))
                try:
                    await self.take_screenshot(f"product_{product.product_number}")
                except Exception as screenshot_err:
                    self.logger.debug(f"Screenshot failed: {screenshot_err}")

            products_since_refresh += 1


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------
def load_script_config(
    config_path: str, cli_overrides: Optional[dict] = None
) -> ScriptConfig:
    if not os.path.exists(config_path):
        raise FileNotFoundError(
            f"Config file not found: {config_path}\n"
            f"Please create a config file by copying configs/default/"
        )

    config_data = load_jsonc(config_path)

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

    actual_cols_after = set(str(c).strip() for c in df.columns)
    missing = required_cols - actual_cols_after
    if missing:
        logger.error(
            f"CSV is missing required columns: {missing}. "
            f"Available: {list(df.columns)}. Cannot parse."
        )
        return []

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
def _normalize_script_name(name: str) -> str:
    """Normalize a script filename for duplicate comparison.

    Strips whitespace, lowercases, and removes known audio extensions.
    """
    name = name.strip().lower()
    for ext in (".mp3", ".wav"):
        if name.endswith(ext):
            name = name[: -len(ext)]
            break
    return name


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
    3. Recursive search from repo root (fallback)
    """
    if not audio_code:
        return None

    audio_dir_path = Path(audio_dir)
    zero_padded = f"{product_number:02d}"

    if audio_dir_path.exists():
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
    else:
        logger.warning(f"Audio directory not found: {audio_dir}")

    # Strategy 3: recursive search from repo root (fallback)
    repo_root = Path(__file__).parent
    for ext in extensions:
        for candidate_path in repo_root.rglob(f"{audio_code}{ext}"):
            logger.debug(f"Found audio (repo search): {candidate_path}")
            return str(candidate_path.resolve())

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
    elapsed_seconds: float = 0.0,
) -> dict:
    """Generate and save a JSON execution report."""
    elapsed_str = f"{int(elapsed_seconds // 60)}m {int(elapsed_seconds % 60):02d}s"
    if mode == "delete" and delete_results is not None:
        successful = sum(1 for r in delete_results if r["success"])
        failed = len(delete_results) - successful
        total_scripts_deleted = sum(r.get("scripts_deleted", 0) for r in delete_results)
        report = {
            "timestamp": datetime.now().isoformat(),
            "mode": "delete",
            "total_products": len(delete_results),
            "successful": successful,
            "failed": failed,
            "total_scripts_deleted": total_scripts_deleted,
            "elapsed_seconds": elapsed_seconds,
            "products": delete_results,
        }
        logger.info("")
        logger.info("=" * 70)
        logger.info("FINAL SCRIPT REPORT (DELETE MODE)")
        logger.info("=" * 70)
        logger.info(
            f"Total: {len(delete_results)} | Success: {successful} | Failed: {failed}"
        )
        logger.info(f"Scripts deleted: {total_scripts_deleted} total")
        logger.info(f"Time: {elapsed_str}")
        for r in delete_results:
            status = "OK" if r["success"] else "FAILED"
            logger.info(
                f"  {status} Product #{r['product_number']}: "
                f"{r['scripts_deleted']} scripts deleted"
            )
            if r.get("error"):
                logger.info(f"      Error: {r['error']}")
        logger.info("-" * 70)
        logger.info(
            f"Total: {len(delete_results)} | Success: {successful} | Failed: {failed} | "
            f"Deleted: {total_scripts_deleted} | Time: {elapsed_str}"
        )
        logger.info("=" * 70)
    else:
        successful = sum(1 for p in products if p.success)
        failed = len(products) - successful
        total_scripts = sum(len(p.rows) for p in products)
        total_skipped = sum(p.scripts_skipped for p in products)
        report = {
            "timestamp": datetime.now().isoformat(),
            "mode": "upload",
            "total_products": len(products),
            "successful": successful,
            "failed": failed,
            "total_scripts": total_scripts,
            "total_skipped": total_skipped,
            "elapsed_seconds": elapsed_seconds,
            "products": [
                {
                    "product_number": p.product_number,
                    "product_name": p.product_name,
                    "scripts": len(p.rows),
                    "scripts_skipped": p.scripts_skipped,
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
        if total_skipped > 0:
            logger.info(f"Scripts: {total_scripts} total ({total_skipped} skipped)")
        else:
            logger.info(f"Scripts: {total_scripts} total")
        logger.info(f"Time: {elapsed_str}")
        for p in products:
            status = "OK" if p.success else "FAILED"
            logger.info(
                f"  {status} Product #{p.product_number} ({p.product_name}): "
                f"{len(p.rows)} scripts"
            )
            if p.error:
                logger.info(f"      Error: {p.error}")
        logger.info("-" * 70)
        summary_parts = [
            f"Total: {len(products)}",
            f"Success: {successful}",
            f"Failed: {failed}",
            f"Scripts: {total_scripts}",
        ]
        if total_skipped > 0:
            summary_parts.append(f"Skipped: {total_skipped}")
        summary_parts.append(f"Time: {elapsed_str}")
        logger.info(" | ".join(summary_parts))
        logger.info("=" * 70)

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
        help="Client name (loads configs/{NAME}/live.json)",
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

    if args.debug and args.headless:
        args.debug = False

    _client: Optional[str] = args.client
    _session_filename, _browser_data_subdir = get_live_session_paths(_client)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    start_time = time.time()
    logger = setup_logging(
        timestamp, logger_name="auto_script", log_prefix="auto_script"
    )

    logger.info("ANYLIVE SCRIPT AUTOMATION (SET LIVE CONTENT)")
    logger.info("=" * 70)

    if _client:
        logger.info(f"Using account: {_client}")

    if args.setup:
        if _client:
            ensure_client_config(_client, config_type="live", logger=logger)
        await setup_login(
            logger,
            login_url=LIVE_LOGIN_URL,
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
        save_last_client(SCRIPT_LAST_CLIENT_FILE, _client)

    config_path: Optional[str] = None
    if args.client:
        config_path = ensure_client_config(
            args.client, config_type="live", logger=logger
        )
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
        logger.info("   python auto_script.py --client example --csv scripts.csv")
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

    if args.debug:
        logger.info("🐛 DEBUG MODE: slow_mo + pause-on-error enabled")

    automation = ScriptAutomation(
        config=config,
        headless=args.headless,
        logger=logger,
        dry_run=args.dry_run,
        debug=args.debug,
        browser_data_subdir=_browser_data_subdir,
        session_filename=_session_filename,
    )

    try:
        await automation.start_browser()

        if not await automation.navigate_to_set_live_content():
            logger.error("Failed to navigate to Set Live Content page")
            return

        if args.delete_scripts:
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
                elapsed_seconds=time.time() - start_time,
            )

        else:
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
                elapsed_seconds=time.time() - start_time,
            )

    finally:
        if args.debug:
            logger.info("")
            logger.info("=" * 70)
            logger.info("🐛 DEBUG MODE: Browser is open for inspection.")
            await async_debug_pause("   Press Enter to close the browser and exit...")
            logger.info("=" * 70)
        await automation.close()


if __name__ == "__main__":
    asyncio.run(main())
