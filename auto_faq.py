#!/usr/bin/env python3
"""AnyLive Product FAQ Automation.

Reads a CSV with product questions and audio codes, navigates to the
Product Q&A page on live.app.anylive.jp, and fills question fields +
uploads audio files for each product.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional

import pandas as pd

from shared import (
    BrowserAutomation,
    SYM,
    async_debug_pause,
    ensure_client_config,
    fmt_banner,
    fmt_elapsed,
    fmt_item,
    fmt_kv,
    fmt_report_footer,
    fmt_report_header,
    fmt_result,
    fmt_section,
    fmt_step,
    fmt_summary,
    get_last_client,
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
    NAVIGATION_TIMEOUT,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
FAQ_LAST_CLIENT_FILE = "state/faq_last_client.json"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class FAQRow:
    product_number: int
    product_name: str
    question: str
    audio_code: str
    row_number: int


@dataclass
class ProductFAQ:
    product_number: int
    product_name: str
    rows: List[FAQRow] = field(default_factory=list)
    success: bool = False
    error: Optional[str] = None


@dataclass
class FAQConfig:
    base_url: str
    audio_dir: str = "downloads"
    audio_extensions: List[str] = field(default_factory=lambda: [".mp3", ".wav"])
    csv_columns: dict = field(
        default_factory=lambda: {
            "product_number": "No.",
            "product_name": "Product Name",
            "question": "Question",
            "audio_code": "Audio Code",
        }
    )
    csv: str = ""


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------
def load_faq_config(
    config_path: str, cli_overrides: Optional[dict] = None
) -> FAQConfig:
    if not os.path.exists(config_path):
        raise FileNotFoundError(
            f"Config file not found: {config_path}\n"
            f"Please create a config file by copying configs/default/"
        )

    config_data = load_jsonc(config_path)

    if cli_overrides:
        config_data.update(cli_overrides)

    return FAQConfig(**config_data)


# ---------------------------------------------------------------------------
# CSV parsing
# ---------------------------------------------------------------------------
def parse_faq_csv(
    df: pd.DataFrame, config: FAQConfig, logger: logging.Logger
) -> List[ProductFAQ]:
    col_product_no = config.csv_columns.get("product_number", "No.")
    col_product_name = config.csv_columns.get("product_name", "Product Name")
    col_question = config.csv_columns.get("question", "Question")
    col_audio = config.csv_columns.get("audio_code", "Audio Code")

    # Header detection (same pattern as auto_tts.py)
    required_cols = {col_product_no, col_product_name, col_question, col_audio}
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

    # Filter rows that have either question or audio code
    valid_rows = df[df[col_question].notna() | df[col_audio].notna()]
    logger.info(f"Valid FAQ rows: {len(valid_rows)}")

    faq_rows: List[FAQRow] = []
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
        question = str(row[col_question]).strip() if pd.notna(row[col_question]) else ""
        audio_code = str(row[col_audio]).strip() if pd.notna(row[col_audio]) else ""

        faq_rows.append(
            FAQRow(
                product_number=product_number,
                product_name=product_name,
                question=question,
                audio_code=audio_code,
                row_number=int(idx) + 2,
            )
        )

    logger.info(f"Total FAQ rows: {len(faq_rows)}")

    # Group by product_number
    from collections import defaultdict

    product_groups: dict[int, List[FAQRow]] = defaultdict(list)
    for row in faq_rows:
        product_groups[row.product_number].append(row)

    products: List[ProductFAQ] = []
    for product_number in sorted(product_groups.keys()):
        rows = product_groups[product_number]
        products.append(
            ProductFAQ(
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
# FAQ selectors
# ---------------------------------------------------------------------------
FAQ_SELECTORS: dict[str, list[str]] = {
    "live_interaction_tab": [
        'text="Live Interaction Settings"',
        ':text("Live Interaction Settings")',
    ],
    "product_qa_tab": [
        'text="Product Q&A"',
        ':text("Product Q&A")',
    ],
    "question_input": [
        '[placeholder*="enter the question"]',
        '[placeholder*="question"]',
    ],
}


# ---------------------------------------------------------------------------
# FAQ Automation class
# ---------------------------------------------------------------------------
class FAQAutomation(BrowserAutomation):
    """Automates Product Q&A filling on live.app.anylive.jp."""

    SELECTORS = FAQ_SELECTORS

    def __init__(
        self,
        config: FAQConfig,
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

    async def navigate_to_product_qa(self) -> bool:
        """Navigate to Product Q&A tab."""
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
            self.logger.info("Already on target page, skipping reload")

        # Click "Live Interaction Settings" top-level tab (generic element, not button/tab)
        try:
            tab = self.page.get_by_text("Live Interaction Settings", exact=True)
            await tab.click(timeout=CLICK_TIMEOUT)
            self.logger.debug("Clicked 'Live Interaction Settings' tab")
        except Exception as e:
            self.logger.warning(
                f"Could not click Live Interaction tab ({e}), may already be active"
            )

        # Wait for sub-tabs to render
        await asyncio.sleep(1.0)

        # Click "Product Q&A" sub-tab (under Q&A Configuration which is default active)
        try:
            sub_tab = self.page.get_by_text("Product Q&A", exact=True)
            await sub_tab.click(timeout=CLICK_TIMEOUT)
            self.logger.debug("Clicked 'Product Q&A' sub-tab")
        except Exception as e:
            self.logger.warning(
                f"Could not click Product Q&A tab ({e}), may already be active"
            )

        await asyncio.sleep(1.0)
        self.logger.info("On Product Q&A page")
        return True

    async def find_product_section(self, product_number: int):
        """Find and scroll to a product section by its number label.

        The Product Q&A page lists products as direct children of a scrollable
        container. Each product child has a header (cover image, number label,
        product name) and optionally a rows section with Q&A entries.

        First locates the product list container (the element with many children
        containing cover images), then matches the specific product by finding
        the number text node that is a sibling of the cover image. Tags the
        matched product element with ``data-faq-product`` for Playwright.

        Returns the product container Locator or None.
        """
        num_str = str(product_number)
        self.logger.debug(f"Looking for product #{product_number}")

        # Clean up any stale markers from previous calls
        await self.page.evaluate(
            """() => {
                document.querySelectorAll('[data-faq-product]').forEach(
                    el => el.removeAttribute('data-faq-product')
                );
            }"""
        )

        found = await self.page.evaluate(
            """(targetNum) => {
                // Step 1: Find the product list container — the element
                // with the MOST direct children that contain cover images.
                // Parent wrappers may also have cover-image descendants but
                // they will have far fewer direct children with them.
                const allDivs = document.querySelectorAll('div');
                let productList = null;
                let maxCover = 0;
                for (const div of allDivs) {
                    if (div.children.length < 1) continue;
                    const withCover = Array.from(div.children).filter(
                        c => c.querySelector('img[alt*="Cover Image"]')
                    );
                    if (withCover.length > maxCover) {
                        productList = div;
                        maxCover = withCover.length;
                    }
                }
                if (!productList) return false;

                // Step 2: Iterate direct children of the product list and
                // match the one whose header contains the target number
                // as a sibling of the cover image.
                for (const child of productList.children) {
                    const walker = document.createTreeWalker(
                        child, NodeFilter.SHOW_TEXT
                    );
                    while (walker.nextNode()) {
                        if (walker.currentNode.textContent.trim() !== targetNum)
                            continue;
                        const parent = walker.currentNode.parentElement;
                        const siblings = parent.parentElement
                            ? Array.from(parent.parentElement.children) : [];
                        const hasCoverSibling = siblings.some(
                            s => s.tagName === 'IMG'
                                && (s.alt || '').includes('Cover Image')
                        );
                        if (hasCoverSibling) {
                            child.setAttribute('data-faq-product', targetNum);
                            return true;
                        }
                    }
                }
                return false;
            }""",
            num_str,
        )

        if not found:
            self.logger.warning(f"Could not find product section for #{product_number}")
            return None

        locator = self.page.locator(f'[data-faq-product="{num_str}"]')
        if await locator.count() == 0:
            self.logger.warning(f"Tagged element disappeared for #{product_number}")
            return None

        await locator.first.scroll_into_view_if_needed()
        # Wait for lazy-rendered Q&A rows to load after scroll
        await asyncio.sleep(1.5)
        return locator.first

    async def add_qa_entries(self, product_section, count: int) -> bool:
        """Click the header 'Add' button within a product section ``count`` times.

        The header "Add" button (uppercase, Chakra UI) triggers a server-side
        Q&A row creation. After each click the button enters a cooldown state
        (opacity animation) and a new question input appears once the server
        responds (~1-2 s). We poll for the new input rather than using a fixed
        sleep to avoid swallowed clicks.
        """
        self.logger.info(fmt_step(SYM.RETRY, f"Adding {count} Q&A entries"))

        add_btn = product_section.get_by_role("button", name="Add", exact=True)
        question_inputs = product_section.get_by_placeholder("enter the question")

        for i in range(count):
            try:
                if await add_btn.count() == 0:
                    self.logger.error(
                        fmt_step(
                            SYM.FAIL, f"Could not find Add button for entry {i + 1}"
                        )
                    )
                    return False

                count_before = await question_inputs.count()
                target = count_before + 1

                # Wait for button cooldown to finish (opacity returns to 1)
                for _ in range(30):
                    opacity = await add_btn.first.evaluate(
                        "b => getComputedStyle(b).opacity"
                    )
                    if opacity == "1":
                        break
                    await asyncio.sleep(0.1)

                await add_btn.first.scroll_into_view_if_needed()
                await add_btn.first.click()
                self.logger.debug(f"Clicked Add ({i + 1}/{count})")

                # Poll until a new question input appears (server round-trip)
                added = False
                for _ in range(16):  # up to ~8 s
                    await asyncio.sleep(0.5)
                    if await question_inputs.count() >= target:
                        added = True
                        break

                if not added:
                    self.logger.error(
                        fmt_step(
                            SYM.FAIL,
                            f"New row did not appear after Add click {i + 1} "
                            f"(expected {target}, got {await question_inputs.count()})",
                        )
                    )
                    return False

            except Exception as e:
                self.logger.error(
                    fmt_step(SYM.FAIL, f"Failed to add Q&A entry {i + 1}: {e}")
                )
                return False

        self.logger.info(fmt_step(SYM.OK, f"Added {count} Q&A entries"))
        return True

    async def fill_qa_row(
        self,
        product_section,
        row_index: int,
        question: str,
        audio_path: Optional[str],
    ) -> bool:
        """Fill a single Q&A row (question + audio upload).

        Question fields are textbox elements (not ``<input>``), matched by
        their placeholder text. We use ``get_by_placeholder`` + ``nth()``
        to target the correct row within the product section.
        """
        row_num = row_index + 1

        # Fill question input — elements have placeholder containing "enter the question"
        try:
            question_inputs = product_section.get_by_placeholder("enter the question")
            input_count = await question_inputs.count()

            if row_index >= input_count:
                self.logger.error(
                    fmt_step(
                        SYM.FAIL,
                        f"Could not find question input for row {row_num} "
                        f"(found {input_count} inputs)",
                    )
                )
                return False

            target_input = question_inputs.nth(row_index)
            await target_input.scroll_into_view_if_needed()
            await target_input.fill(question)
            self.logger.debug(f"Filled question for row {row_num}: {question[:50]}")
        except Exception as e:
            self.logger.error(
                fmt_step(SYM.FAIL, f"Error filling question row {row_num}: {e}")
            )
            return False

        # Upload audio file
        if audio_path and not self.dry_run:
            try:
                ok = await self._upload_audio(product_section, row_index, audio_path)
                if not ok:
                    self.logger.warning(
                        fmt_step(
                            SYM.FAIL,
                            f"Audio upload failed for row {row_num}, continuing",
                        )
                    )
            except Exception as e:
                self.logger.warning(
                    fmt_step(SYM.FAIL, f"Audio upload error for row {row_num}: {e}")
                )
        elif audio_path and self.dry_run:
            self.logger.info(
                fmt_step(
                    SYM.SKIP, f"Dry-run: would upload {audio_path} for row {row_num}"
                )
            )

        return True

    async def _wait_for_upload_confirmation(
        self,
        product_section,
        audio_filename: str,
        timeout_ms: int = 20000,
    ) -> bool:
        """Poll until *audio_filename* text appears in the product section,
        confirming the OSS upload completed and the server persisted the file.

        The page renders the filename (e.g. ``SFD4.mp3``) as a ``<p>`` once
        the upload finishes.  This is more reliable than checking button names
        which may match across product boundaries.
        """
        interval = 0.5
        elapsed = 0.0
        max_wait = timeout_ms / 1000
        while elapsed < max_wait:
            found = await product_section.get_by_text(
                audio_filename, exact=True
            ).count()
            if found > 0:
                return True
            await asyncio.sleep(interval)
            elapsed += interval
        return False

    async def _upload_audio(
        self, product_section, row_index: int, audio_path: str
    ) -> bool:
        """Upload an audio file for a Q&A row.

        After setting the file via the native file chooser, poll until the
        audio filename text appears in the product section DOM — this confirms
        the OSS upload completed and the server persisted the file.
        """
        row_num = row_index + 1
        audio_filename = os.path.basename(audio_path)
        self.logger.debug(f"Uploading audio for row {row_num}: {audio_path}")

        # Capture upload-related console logs for debugging
        console_msgs: list[str] = []

        def _on_console(msg) -> None:
            text = msg.text
            if any(kw in text.lower() for kw in ("upload", "oss", "上传")):
                console_msgs.append(text[:120])

        self.page.on("console", _on_console)
        try:
            result = await self._do_upload(
                product_section,
                row_index,
                audio_path,
                audio_filename,
                console_msgs,
            )
        finally:
            self.page.remove_listener("console", _on_console)
        return result

    async def _do_upload(
        self,
        product_section,
        row_index: int,
        audio_path: str,
        audio_filename: str,
        console_msgs: list[str],
    ) -> bool:
        """Try 3 strategies to upload audio, confirming via filename text.

        1. Click ``upload-audio`` button (new empty rows) — always ``.first``
           because previous rows' buttons change to exchange-audio after upload.
        2. Click ``exchange-audio`` button (replace existing audio).
        3. Hidden ``input[type=file]`` fallback indexed by ``row_index``.
        """
        row_num = row_index + 1

        # Strategy 1: Click upload-audio button (new empty rows)
        try:
            upload_btns = product_section.get_by_role("button", name="upload-audio")
            btn_count = await upload_btns.count()
            if btn_count > 0:
                async with self.page.expect_file_chooser(timeout=5000) as fc_info:
                    await upload_btns.first.click()
                file_chooser = await fc_info.value
                await file_chooser.set_files(audio_path)
                self.logger.debug(
                    f"File set for row {row_num}, waiting for OSS upload "
                    f"({audio_filename})..."
                )
                if await self._wait_for_upload_confirmation(
                    product_section, audio_filename
                ):
                    self.logger.info(
                        fmt_step(SYM.OK, f"Uploaded audio for row {row_num}")
                    )
                    return True
                if console_msgs:
                    self.logger.debug(f"Console during upload: {console_msgs}")
                self.logger.warning(
                    f"Upload confirmation timeout for row {row_num} — "
                    f"'{audio_filename}' not found in DOM after 20s"
                )
                return False
        except Exception as e:
            self.logger.debug(f"Upload-audio strategy failed for row {row_num}: {e}")

        # Strategy 2: Click exchange-audio button (replacing existing audio)
        try:
            exchange_btns = product_section.get_by_role("button", name="exchange-audio")
            if await exchange_btns.count() > 0:
                async with self.page.expect_file_chooser(timeout=5000) as fc_info:
                    await exchange_btns.first.click()
                file_chooser = await fc_info.value
                await file_chooser.set_files(audio_path)
                self.logger.debug(
                    f"File set for replacement on row {row_num}, "
                    f"waiting for confirmation..."
                )
                if await self._wait_for_upload_confirmation(
                    product_section, audio_filename
                ):
                    self.logger.info(
                        fmt_step(SYM.OK, f"Replaced audio for row {row_num}")
                    )
                    return True
                self.logger.warning(
                    f"Replacement confirmation timeout for row {row_num}"
                )
                return False
        except Exception as e:
            self.logger.debug(f"Exchange-audio strategy failed for row {row_num}: {e}")

        # Strategy 3: Find hidden input[type=file]
        try:
            file_inputs = product_section.locator('input[type="file"]')
            if await file_inputs.count() > row_index:
                await file_inputs.nth(row_index).set_input_files(audio_path)
                self.logger.debug(
                    f"File set via hidden input for row {row_num}, "
                    f"waiting for confirmation..."
                )
                if await self._wait_for_upload_confirmation(
                    product_section, audio_filename
                ):
                    self.logger.info(
                        fmt_step(
                            SYM.OK,
                            f"Uploaded audio for row {row_num} (via hidden input)",
                        )
                    )
                    return True
                self.logger.warning(
                    f"Hidden input confirmation timeout for row {row_num}"
                )
                return False
        except Exception as e:
            self.logger.debug(f"Hidden input strategy failed for row {row_num}: {e}")

        self.logger.warning(
            fmt_step(SYM.FAIL, f"Could not upload audio for row {row_num}")
        )
        return False

    async def _upload_missing_audio(
        self,
        product_section,
        product_faq: ProductFAQ,
    ) -> tuple[int, int]:
        """Upload audio for rows that have questions filled but no audio.

        Returns ``(needed, uploaded)`` — the number of rows that needed audio
        and how many were successfully uploaded.
        """
        upload_btns = product_section.get_by_role("button", name="upload-audio")
        missing_count = await upload_btns.count()
        if missing_count == 0:
            return (0, 0)

        self.logger.info(
            fmt_step(
                SYM.RETRY,
                f"Product #{product_faq.product_number}: {missing_count} rows "
                f"have questions but missing audio, uploading",
            )
        )

        # Determine which rows are missing audio by checking if the
        # audio filename text is already visible in the section.
        question_inputs = product_section.get_by_placeholder("enter the question")
        total_rows = await question_inputs.count()

        rows_needing_audio: list[tuple[int, str]] = []  # (row_idx, audio_path)
        for row_idx in range(min(total_rows, len(product_faq.rows))):
            faq_row = product_faq.rows[row_idx]
            if not faq_row.audio_code:
                continue
            audio_path = resolve_audio_file(
                faq_row.audio_code,
                faq_row.product_number,
                self.config.audio_dir,
                self.config.audio_extensions,
                self.logger,
            )
            if not audio_path:
                self.logger.warning(
                    fmt_step(
                        SYM.FAIL,
                        f"No audio file for row {row_idx + 1} (code: {faq_row.audio_code})",
                    )
                )
                continue
            # Skip if audio filename already visible (already uploaded)
            audio_filename = os.path.basename(audio_path)
            already_has = await product_section.get_by_text(
                audio_filename, exact=True
            ).count()
            if already_has > 0:
                continue
            rows_needing_audio.append((row_idx, audio_path))

        if not rows_needing_audio:
            return (0, 0)  # all rows already have audio

        uploaded = 0
        section = product_section
        for row_idx, audio_path in rows_needing_audio:
            try:
                ok = await self._upload_audio(section, row_idx, audio_path)
                if ok:
                    uploaded += 1
            except Exception as e:
                self.logger.warning(
                    fmt_step(
                        SYM.FAIL, f"Failed to upload audio for row {row_idx + 1}: {e}"
                    )
                )

            # Re-find section after upload (DOM may have changed)
            section = await self.find_product_section(product_faq.product_number)
            if section is None:
                self.logger.error(
                    fmt_step(
                        SYM.FAIL,
                        f"Lost product #{product_faq.product_number} "
                        f"after uploading audio for row {row_idx + 1}",
                    )
                )
                break

        self.logger.info(
            fmt_step(
                SYM.OK if uploaded == len(rows_needing_audio) else SYM.FAIL,
                f"Product #{product_faq.product_number}: uploaded {uploaded}/"
                f"{len(rows_needing_audio)} missing audio files",
            )
        )
        return (len(rows_needing_audio), uploaded)

    async def process_product(
        self, product_faq: ProductFAQ, index: int, total: int
    ) -> bool:
        """Process all Q&A entries for a single product."""
        self.logger.info(
            fmt_item(
                index,
                total,
                f"Product #{product_faq.product_number} — "
                f"{product_faq.product_name} ({len(product_faq.rows)} questions)",
            )
        )

        try:
            # Find product section on page
            section = await self.find_product_section(product_faq.product_number)
            if section is None:
                product_faq.error = (
                    f"Product #{product_faq.product_number} not found on page"
                )
                self.logger.error(fmt_step(SYM.FAIL, product_faq.error))
                return False

            # Check for existing Q&A rows (from previous runs or partial fills)
            existing_inputs = section.get_by_placeholder("enter the question")
            existing_count = await existing_inputs.count()

            # Count how many rows already have question text (filled rows)
            filled_count = 0
            for idx in range(existing_count):
                val = await existing_inputs.nth(idx).input_value()
                if val.strip():
                    filled_count += 1

            rows_needed = len(product_faq.rows)
            fill_offset = 0

            if filled_count >= rows_needed:
                # Questions are filled — but audio may be missing from
                # earlier buggy runs.  Check for upload-audio buttons
                # (present when no audio is attached) and re-upload.
                if not self.dry_run:
                    needed, uploaded = await self._upload_missing_audio(
                        section, product_faq
                    )
                    if needed == 0:
                        self.logger.info(
                            fmt_step(
                                SYM.SKIP,
                                f"Already has {filled_count} filled rows with audio",
                            )
                        )
                    elif uploaded < needed:
                        product_faq.error = (
                            f"{needed - uploaded}/{needed} audio uploads failed"
                        )
                    # else: all uploads succeeded, logged inside method
                else:
                    self.logger.info(
                        fmt_step(
                            SYM.SKIP,
                            f"Already has {filled_count} filled rows, skipping (dry-run)",
                        )
                    )
                product_faq.success = product_faq.error is None
                return product_faq.success
            elif filled_count > 0:
                fill_offset = filled_count
                self.logger.warning(
                    fmt_step(
                        SYM.WARN,
                        f"Product #{product_faq.product_number} has {filled_count} "
                        f"filled rows, will fill remaining {rows_needed - filled_count}",
                    )
                )

            # We need (rows_needed - fill_offset) total rows to fill.
            # Some empty rows may already exist from a previous partial run.
            # Only click Add for rows beyond what already exist in the DOM.
            rows_to_add = rows_needed - existing_count
            if rows_to_add > 0:
                self.logger.info(
                    fmt_step(
                        SYM.RETRY,
                        f"Need {rows_needed} total rows, {existing_count} exist "
                        f"({filled_count} filled, {existing_count - filled_count} empty), "
                        f"clicking Add {rows_to_add} times",
                    )
                )
                if not await self.add_qa_entries(section, rows_to_add):
                    product_faq.error = "Failed to add Q&A entries"
                    self.logger.error(fmt_step(SYM.FAIL, product_faq.error))
                    return False

            # Fill only the unfilled rows (starting from fill_offset).
            # Re-find the product section after each row because audio
            # uploads trigger React re-renders that replace DOM elements,
            # invalidating the data-faq-product attribute and locator.
            successful = fill_offset  # count filled rows as already done
            for i in range(fill_offset, rows_needed):
                faq_row = product_faq.rows[i]
                audio_path = resolve_audio_file(
                    faq_row.audio_code,
                    faq_row.product_number,
                    self.config.audio_dir,
                    self.config.audio_extensions,
                    self.logger,
                )

                ok = await self.fill_qa_row(section, i, faq_row.question, audio_path)
                if ok:
                    successful += 1

                # Re-find section for next iteration (DOM may have changed)
                if i < rows_needed - 1:
                    section = await self.find_product_section(
                        product_faq.product_number
                    )
                    if section is None:
                        self.logger.error(
                            fmt_step(
                                SYM.FAIL,
                                f"Lost product #{product_faq.product_number} "
                                f"after filling row {i + 1}",
                            )
                        )
                        break

            self.logger.info(
                fmt_step(SYM.OK, f"Filled {successful}/{rows_needed} questions")
            )
            self.logger.info(
                fmt_result(
                    successful == rows_needed,
                    f"{successful}/{rows_needed} questions filled",
                )
            )

            product_faq.success = successful == rows_needed
            if not product_faq.success:
                product_faq.error = f"{rows_needed - successful} questions failed"
            return product_faq.success

        except Exception as e:
            product_faq.error = str(e)
            self.logger.error(
                fmt_step(
                    SYM.FAIL,
                    f"Error processing product #{product_faq.product_number}: {e}",
                )
            )
            try:
                await self.take_screenshot(f"product_{product_faq.product_number}")
            except Exception as screenshot_err:
                self.logger.debug(f"Failed to take error screenshot: {screenshot_err}")
            return False


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------
def generate_faq_report(
    products: List[ProductFAQ],
    config: FAQConfig,
    timestamp: str,
    logger: logging.Logger,
    logs_dir: Optional[str] = None,
    elapsed_seconds: float = 0.0,
) -> dict:
    successful = sum(1 for p in products if p.success)
    failed = len(products) - successful
    total_questions = sum(len(p.rows) for p in products)

    report = {
        "timestamp": datetime.now().isoformat(),
        "total_products": len(products),
        "successful": successful,
        "failed": failed,
        "total_questions": total_questions,
        "elapsed_seconds": elapsed_seconds,
        "products": [
            {
                "product_number": p.product_number,
                "product_name": p.product_name,
                "questions": len(p.rows),
                "success": p.success,
                "error": p.error,
            }
            for p in products
        ],
    }

    elapsed_str = fmt_elapsed(elapsed_seconds)
    logger.info(fmt_report_header("FINAL FAQ REPORT"))
    logger.info(
        fmt_summary(
            f"Total: {len(products)}",
            f"Success: {successful} {SYM.OK}",
            f"Failed: {failed} {SYM.FAIL}",
        )
    )
    logger.info(fmt_summary(f"Questions: {total_questions}", f"Time: {elapsed_str}"))
    logger.info("")

    for p in products:
        ok = not p.error
        detail = (
            f"Product #{p.product_number} ({p.product_name}): {len(p.rows)} questions"
        )
        logger.info(fmt_result(ok, detail))
        if p.error:
            logger.info(f"      Error: {p.error}")

    logs_path = Path(logs_dir) if logs_dir else Path("logs")
    logs_path.mkdir(exist_ok=True)
    report_path = logs_path / f"faq_report_{timestamp}.json"

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    logger.info("")
    logger.info(f"  Report saved: {report_path}")
    logger.info(fmt_report_footer())
    return report


# ---------------------------------------------------------------------------
# Job wrapper
# ---------------------------------------------------------------------------
async def run_job(
    config_path: str,
    csv_path: str,
    *,
    client: str | None = None,
    headless: bool = False,
    dry_run: bool = False,
    debug: bool = False,
    start_product: int | None = None,
    limit: int | None = None,
    audio_dir: str | None = None,
    app_support_dir: str | None = None,
    quiet: bool = False,
    verbose: bool = False,
    no_color: bool = False,
    log_callback: Callable[[str, str], None] | None = None,
    cancel_check: Callable[[], bool] | None = None,
) -> dict:
    """Run FAQ automation as a job.

    Args:
        config_path: Path to FAQ config JSON file
        csv_path: Path to CSV file with product questions
        headless: Run browser in headless mode
        dry_run: Fill questions only, skip audio upload
        debug: Keep browser open after execution for debugging
        start_product: Starting product number (1-indexed)
        limit: Limit number of products to process
        audio_dir: Override audio directory path
        app_support_dir: Directory for logs and browser data (default: current dir)
        log_callback: Optional callback for streaming logs to GUI

    Returns:
        dict with keys: success (bool), report (dict), error (str or None)
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    start_time = time.time()
    verbosity = "quiet" if quiet else ("verbose" if verbose else "normal")
    logger = setup_logging(
        timestamp,
        logger_name="auto_faq",
        log_prefix="auto_faq",
        log_callback=log_callback,
        color=not no_color,
        verbosity=verbosity,
    )

    logger.info(fmt_banner("ANYLIVE FAQ AUTOMATION", Client=client or ""))

    try:
        # Load configuration
        if not os.path.exists(config_path):
            error_msg = f"Config file not found: {config_path}"
            logger.error(error_msg)
            return {"success": False, "report": None, "error": error_msg}

        cli_overrides: dict = {}
        if audio_dir:
            cli_overrides["audio_dir"] = audio_dir

        try:
            config = load_faq_config(
                config_path, cli_overrides if cli_overrides else None
            )
        except FileNotFoundError as e:
            error_msg = str(e)
            logger.error(error_msg)
            return {"success": False, "report": None, "error": error_msg}
        except Exception as e:
            error_msg = f"Failed to load config: {e}"
            logger.error(error_msg)
            return {"success": False, "report": None, "error": error_msg}

        # Load CSV
        if not os.path.exists(csv_path):
            error_msg = f"CSV file not found: {csv_path}"
            logger.error(error_msg)
            return {"success": False, "report": None, "error": error_msg}

        try:
            df = load_csv(csv_path, logger)
            products = parse_faq_csv(df, config, logger)
        except Exception as e:
            error_msg = f"Failed to parse CSV: {e}"
            logger.error(error_msg)
            return {"success": False, "report": None, "error": error_msg}

        if not products:
            error_msg = "No products to process"
            logger.error(error_msg)
            return {"success": False, "report": None, "error": error_msg}

        # Apply start-product filter (by product number, not index)
        if start_product is None:
            start_product = 1
        if start_product > 1:
            products = [p for p in products if p.product_number >= start_product]

        if limit:
            products = products[:limit]

        kv = [("Config", str(config_path)), ("CSV", str(csv_path))]
        if dry_run:
            kv.append(("Mode", "dry-run"))
        if debug:
            kv.append(("Debug", "on"))
        if start_product and start_product > 1:
            kv.append(("Start Product", str(start_product)))
        if limit:
            kv.append(("Limit", str(limit)))
        logger.info(fmt_kv(kv))
        logger.info(fmt_section(f"Processing {len(products)} products"))

        # Determine browser data directory
        _browser_data_subdir = None
        _session_filename = LIVE_SESSION_FILE
        if app_support_dir:
            _browser_data_subdir = os.path.join(app_support_dir, LIVE_BROWSER_DATA)
            _session_filename = os.path.join(app_support_dir, LIVE_SESSION_FILE)

        # Run automation
        automation = FAQAutomation(
            config=config,
            headless=headless,
            logger=logger,
            dry_run=dry_run,
            debug=debug,
            browser_data_subdir=_browser_data_subdir,
            session_filename=_session_filename,
        )

        cancelled = False
        try:
            await automation.start_browser()

            if not await automation.navigate_to_product_qa():
                error_msg = "Failed to navigate to Product Q&A page"
                logger.error(error_msg)
                return {"success": False, "report": None, "error": error_msg}

            for idx, product in enumerate(products, start=1):
                if cancel_check and cancel_check():
                    logger.info("Job cancelled, stopping")
                    cancelled = True
                    break
                result = await automation.process_product(product, idx, len(products))
                if not result and debug:
                    logger.info(
                        fmt_step(
                            SYM.WARN,
                            f"Debug pause: Product #{product.product_number} failed",
                        )
                    )
                    await async_debug_pause(
                        "   Press Enter to continue to next product..."
                    )

        finally:
            if debug and not cancelled:
                succeeded = sum(1 for p in products if p.success)
                failed = [f"#{p.product_number}" for p in products if p.error]
                logger.info(fmt_report_header("DEBUG RESULTS"))
                logger.info(
                    fmt_summary(
                        f"Succeeded: {succeeded}/{len(products)}",
                        f"Failed: {len(failed)} {SYM.FAIL}",
                    )
                )
                if failed:
                    logger.info(fmt_summary(f"Failed IDs: {', '.join(failed)}"))
                logger.info(
                    fmt_step(SYM.WARN, "Debug mode: browser is open for inspection")
                )
                await async_debug_pause(
                    "   Press Enter to close the browser and exit..."
                )
                logger.info(fmt_report_footer())
            await automation.close()

        # Generate report
        report = generate_faq_report(
            products,
            config,
            timestamp,
            logger,
            elapsed_seconds=time.time() - start_time,
        )

        return {"success": True, "report": report, "error": None}

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Job failed: {error_msg}")
        return {"success": False, "report": None, "error": error_msg}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
async def main() -> None:
    parser = argparse.ArgumentParser(description="AnyLive Product FAQ Automation")
    parser.add_argument("--setup", action="store_true", help="One-time login setup")
    parser.add_argument(
        "--csv", type=str, help="Path to CSV file (auto-detects if not specified)"
    )
    parser.add_argument(
        "--start-product", type=int, default=1, help="Starting product number"
    )
    parser.add_argument("--limit", type=int, help="Limit number of products to process")
    parser.add_argument(
        "--headless", action="store_true", help="Run browser in headless mode"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fill questions only, skip audio upload",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Keep browser open after execution for debugging",
    )
    parser.add_argument("--audio-dir", type=str, help="Override audio directory path")
    parser.add_argument("--config", type=str, help="Path to FAQ config JSON file")
    parser.add_argument(
        "--client",
        type=str,
        help="Client name (loads configs/{NAME}/live.json)",
    )
    parser.add_argument("--base-url", type=str, help="Override base URL")
    parser.add_argument(
        "--quiet", action="store_true", help="Show warnings and final report only"
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Show debug-level output"
    )
    parser.add_argument(
        "--no-color", action="store_true", help="Disable colored output"
    )

    args = parser.parse_args()

    if args.debug and args.headless:
        args.debug = False

    _explicit_client: Optional[str] = args.client
    _client: Optional[str] = _explicit_client or get_last_client(FAQ_LAST_CLIENT_FILE)
    _session_filename, _browser_data_subdir = get_live_session_paths(_client)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    verbosity = "quiet" if args.quiet else ("verbose" if args.verbose else "normal")
    logger = setup_logging(
        timestamp,
        logger_name="auto_faq",
        log_prefix="auto_faq",
        color=not args.no_color,
        verbosity=verbosity,
    )

    logger.info(fmt_banner("ANYLIVE FAQ AUTOMATION", Client=_client or ""))
    kv_main: list[tuple[str, str]] = []
    if _client:
        kv_main.append(("Client", _client))
    if args.setup:
        kv_main.append(("Mode", "setup"))
    if kv_main:
        logger.info(fmt_kv(kv_main))

    if args.setup:
        if _explicit_client:
            ensure_client_config(_explicit_client, config_type="live", logger=logger)
        await setup_login(
            logger,
            login_url=LIVE_LOGIN_URL,
            browser_data_subdir=_browser_data_subdir,
            session_filename=_session_filename,
        )
        return

    if not is_session_valid(_session_filename):
        logger.error("No FAQ session found. Please run with --setup first.")
        logger.info(
            f"   python auto_faq.py --setup --client {_client or '<brand_name>'}"
        )
        return

    if _explicit_client:
        save_last_client(FAQ_LAST_CLIENT_FILE, _explicit_client)

    config_path: str
    if args.client:
        config_path = ensure_client_config(
            args.client, config_type="live", logger=logger
        )
    elif args.config:
        config_path = args.config
    else:
        config_path = "configs/default/live.json"

    # CSV selection: CLI flag > config.csv > autodetect
    try:
        csv_from_config = None
        try:
            _cfg_raw = load_jsonc(config_path)
            csv_from_config = _cfg_raw.get("csv")
        except Exception:
            csv_from_config = None

        csv_path = find_csv_file(args.csv or csv_from_config)
    except (FileNotFoundError, ValueError) as e:
        logger.error(f"{e}")
        return

    result = await run_job(
        config_path=config_path,
        csv_path=csv_path,
        client=_client,
        headless=args.headless,
        dry_run=args.dry_run,
        debug=args.debug,
        start_product=args.start_product if args.start_product > 1 else None,
        limit=args.limit,
        audio_dir=args.audio_dir,
        app_support_dir=None,
        quiet=args.quiet,
        verbose=args.verbose,
        no_color=args.no_color,
        log_callback=None,
    )

    if not result["success"]:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
