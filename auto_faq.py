#!/usr/bin/env python3
"""AnyLive Product FAQ Automation.

Reads a CSV with product questions and audio codes, navigates to the
Product Q&A page on live.app.anylive.jp, and fills question fields +
uploads audio files for each product.
"""
import argparse
import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import pandas as pd

from shared import (
    BrowserAutomation,
    setup_login,
    setup_logging,
    find_csv_file,
    load_csv,
    is_session_valid,
    NAVIGATION_TIMEOUT,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
FAQ_SESSION_FILE = "session_state_faq.json"
FAQ_BROWSER_DATA = "browser_data_faq"
FAQ_LOGIN_URL = "https://live.app.anylive.jp"

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
            f"Please create a config file or use the template at configs/faq_template.json"
        )

    with open(config_path, "r", encoding="utf-8") as f:
        config_data = json.load(f)

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
# FAQ selectors
# ---------------------------------------------------------------------------
FAQ_SELECTORS: dict[str, list[str]] = {
    "live_interaction_tab": [
        'text="Live Interaction Settings"',
        'button:has-text("Live Interaction")',
        '[role="tab"]:has-text("Live Interaction")',
    ],
    "product_qa_tab": [
        'text="Product Q&A"',
        'button:has-text("Product Q&A")',
        '[role="tab"]:has-text("Product Q&A")',
    ],
    "question_input": [
        'input[placeholder*="enter the question"]',
        'input[placeholder*="Enter the question"]',
        'input[placeholder*="question"]',
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
        screenshots_dir: Optional[str] = None,
    ) -> None:
        super().__init__(
            headless=headless,
            logger=logger,
            dry_run=dry_run,
            screenshots_dir=screenshots_dir,
            browser_data_subdir=FAQ_BROWSER_DATA,
            session_filename=FAQ_SESSION_FILE,
            login_url=FAQ_LOGIN_URL,
            base_url=config.base_url,
        )
        self.config = config

    async def navigate_to_product_qa(self) -> bool:
        """Navigate to Product Q&A tab."""
        self.logger.info(f"Navigating to {self.config.base_url}")
        await self.page.goto(
            self.config.base_url,
            wait_until="domcontentloaded",
            timeout=NAVIGATION_TIMEOUT,
        )
        await asyncio.sleep(1.0)

        # Click "Live Interaction Settings" tab
        if not await self.safe_click(
            "live_interaction_tab", "Live Interaction Settings tab"
        ):
            self.logger.warning(
                "Could not find Live Interaction tab, may already be on the page"
            )

        await asyncio.sleep(0.5)

        # Click "Product Q&A" sub-tab
        if not await self.safe_click("product_qa_tab", "Product Q&A tab"):
            self.logger.warning(
                "Could not find Product Q&A tab, may already be on the page"
            )

        await asyncio.sleep(1.0)
        self.logger.info("On Product Q&A page")
        return True

    async def find_product_section(self, product_number: int):
        """Find and scroll to a product section by its number label.

        Returns the product container locator or None.
        """
        self.logger.debug(f"Looking for product #{product_number}")

        # Products are listed with their number as a label.
        # Try multiple strategies to find the correct product section.

        # Strategy 1: Find by exact text matching the product number
        # Products often appear as numbered sections (1, 2, 3...)
        product_locator = None

        # Look for a container that has the product number as text
        # The product sections typically have a number label followed by product name
        try:
            # Try to find all product sections and match by number
            sections = await self.page.evaluate(
                """(targetNum) => {
                    // Look for elements containing just the number
                    const allElements = document.querySelectorAll('*');
                    for (const el of allElements) {
                        const text = el.textContent.trim();
                        // Match elements that start with the product number
                        if (el.children.length > 0 && el.querySelector('button')) {
                            // This might be a product container with an Add button
                            const numEl = el.querySelector('span, div, p, h3, h4');
                            if (numEl) {
                                const numText = numEl.textContent.trim();
                                // Check if the number matches (as integer)
                                if (parseInt(numText) === targetNum) {
                                    // Mark it for Playwright to find
                                    el.setAttribute('data-faq-product', targetNum.toString());
                                    return true;
                                }
                            }
                        }
                    }
                    return false;
                }""",
                product_number,
            )

            if sections:
                product_locator = self.page.locator(
                    f'[data-faq-product="{product_number}"]'
                )
                if await product_locator.count() > 0:
                    await product_locator.first.scroll_into_view_if_needed()
                    await asyncio.sleep(0.3)
                    return product_locator.first
        except Exception as e:
            self.logger.debug(f"Product section search strategy 1 failed: {e}")

        # Strategy 2: Use text content matching
        try:
            # Look for the number text as a standalone element
            num_str = str(product_number)
            candidates = self.page.locator(f'text="{num_str}"')
            count = await candidates.count()

            for i in range(count):
                candidate = candidates.nth(i)
                try:
                    text = await candidate.text_content()
                    if text and text.strip() == num_str:
                        # Found the number label, navigate up to the product container
                        # that has an "+ Add" button
                        container = await candidate.evaluate_handle(
                            """(el) => {
                                let p = el;
                                for (let i = 0; i < 10; i++) {
                                    if (!p.parentElement) break;
                                    p = p.parentElement;
                                    // Check if this container has an Add button
                                    const addBtn = p.querySelector('button');
                                    if (addBtn && (addBtn.textContent.includes('Add') ||
                                                   addBtn.textContent.includes('+'))) {
                                        return p;
                                    }
                                }
                                return null;
                            }"""
                        )
                        if container:
                            await candidate.scroll_into_view_if_needed()
                            await asyncio.sleep(0.3)
                            return container
                except Exception:
                    continue
        except Exception as e:
            self.logger.debug(f"Product section search strategy 2 failed: {e}")

        self.logger.warning(f"Could not find product section for #{product_number}")
        return None

    async def add_qa_entries(self, product_section, count: int) -> bool:
        """Click '+ Add' button within a product section ``count`` times."""
        self.logger.info(f"Adding {count} Q&A entries...")

        for i in range(count):
            try:
                # Try to find the Add button within the product section
                add_btn = None

                # Strategy 1: Find button with "+ Add" text in the section
                try:
                    add_btn = await product_section.query_selector(
                        'button:has-text("Add")'
                    )
                except Exception:
                    pass

                if not add_btn:
                    try:
                        add_btn = await product_section.query_selector(
                            'button:has-text("+")'
                        )
                    except Exception:
                        pass

                if add_btn:
                    await add_btn.scroll_into_view_if_needed()
                    await add_btn.click()
                    self.logger.debug(f"Clicked + Add ({i + 1}/{count})")
                else:
                    self.logger.error(f"Could not find + Add button for entry {i + 1}")
                    return False

                # Wait for the new row to appear
                await asyncio.sleep(0.5)

            except Exception as e:
                self.logger.error(f"Failed to add Q&A entry {i + 1}: {e}")
                return False

        self.logger.info(f"Added {count} Q&A entries")
        return True

    async def fill_qa_row(
        self,
        product_section,
        row_index: int,
        question: str,
        audio_path: Optional[str],
    ) -> bool:
        """Fill a single Q&A row (question + audio upload)."""
        row_num = row_index + 1

        # Fill question input
        try:
            question_inputs = await product_section.query_selector_all(
                'input[placeholder*="question"], input[placeholder*="Question"]'
            )

            if row_index < len(question_inputs):
                question_input = question_inputs[row_index]
                ok = await self.clear_and_fill(question_input, question)
                if not ok:
                    self.logger.error(f"Failed to fill question for row {row_num}")
                    return False
                self.logger.debug(f"Filled question for row {row_num}: {question[:50]}")
            else:
                self.logger.error(
                    f"Could not find question input for row {row_num} "
                    f"(found {len(question_inputs)} inputs)"
                )
                return False
        except Exception as e:
            self.logger.error(f"Error filling question row {row_num}: {e}")
            return False

        # Upload audio file
        if audio_path and not self.dry_run:
            try:
                ok = await self._upload_audio(product_section, row_index, audio_path)
                if not ok:
                    self.logger.warning(
                        f"Audio upload failed for row {row_num}, continuing"
                    )
            except Exception as e:
                self.logger.warning(f"Audio upload error for row {row_num}: {e}")
        elif audio_path and self.dry_run:
            self.logger.info(f"DRY RUN: Would upload {audio_path} for row {row_num}")

        return True

    async def _upload_audio(
        self, product_section, row_index: int, audio_path: str
    ) -> bool:
        """Upload an audio file for a Q&A row.

        Primary: Use page.expect_file_chooser() event.
        Fallback: Find hidden input[type=file] and use set_input_files().
        """
        row_num = row_index + 1
        self.logger.debug(f"Uploading audio for row {row_num}: {audio_path}")

        # Strategy 1: Find upload button/area and use file chooser
        try:
            upload_areas = await product_section.query_selector_all(
                'button:has-text("Upload"), '
                '[class*="upload"], '
                '[class*="audio"] button, '
                'button:has-text("Voice Reply")'
            )

            if row_index < len(upload_areas):
                upload_area = upload_areas[row_index]
                async with self.page.expect_file_chooser(timeout=5000) as fc_info:
                    await upload_area.click()
                file_chooser = await fc_info.value
                await file_chooser.set_files(audio_path)
                self.logger.info(f"Uploaded audio for row {row_num}")
                await asyncio.sleep(0.5)
                return True
        except Exception as e:
            self.logger.debug(f"File chooser strategy failed for row {row_num}: {e}")

        # Strategy 2: Find hidden input[type=file]
        try:
            file_inputs = await product_section.query_selector_all('input[type="file"]')
            if row_index < len(file_inputs):
                await file_inputs[row_index].set_input_files(audio_path)
                self.logger.info(f"Uploaded audio for row {row_num} (via hidden input)")
                await asyncio.sleep(0.5)
                return True
        except Exception as e:
            self.logger.debug(f"Hidden input strategy failed for row {row_num}: {e}")

        self.logger.warning(f"Could not upload audio for row {row_num}")
        return False

    async def process_product(self, product_faq: ProductFAQ) -> bool:
        """Process all Q&A entries for a single product."""
        self.logger.info(
            f"Processing product #{product_faq.product_number}: "
            f"{product_faq.product_name} ({len(product_faq.rows)} questions)"
        )

        try:
            # Find product section on page
            section = await self.find_product_section(product_faq.product_number)
            if section is None:
                product_faq.error = (
                    f"Product #{product_faq.product_number} not found on page"
                )
                self.logger.error(product_faq.error)
                return False

            # Click "+ Add" for each question
            if not await self.add_qa_entries(section, len(product_faq.rows)):
                product_faq.error = "Failed to add Q&A entries"
                self.logger.error(product_faq.error)
                return False

            # Fill each row
            successful = 0
            for i, faq_row in enumerate(product_faq.rows):
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

            self.logger.info(
                f"Product #{product_faq.product_number}: "
                f"{successful}/{len(product_faq.rows)} questions filled"
            )

            product_faq.success = successful == len(product_faq.rows)
            if not product_faq.success:
                product_faq.error = (
                    f"{len(product_faq.rows) - successful} questions failed"
                )
            return product_faq.success

        except Exception as e:
            product_faq.error = str(e)
            self.logger.error(
                f"Error processing product #{product_faq.product_number}: {e}"
            )
            try:
                await self.take_screenshot(f"product_{product_faq.product_number}")
            except Exception:
                pass
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
) -> dict:
    successful = sum(1 for p in products if p.success)
    failed = len(products) - successful

    report = {
        "timestamp": datetime.now().isoformat(),
        "total_products": len(products),
        "successful": successful,
        "failed": failed,
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

    logger.info("")
    logger.info("=" * 70)
    logger.info("FINAL FAQ REPORT")
    logger.info("=" * 70)
    logger.info(f"Total: {len(products)} | Success: {successful} | Failed: {failed}")

    for p in products:
        status = "OK" if p.success else "FAILED"
        logger.info(
            f"  {status} Product #{p.product_number} ({p.product_name}): "
            f"{len(p.rows)} questions"
        )
        if p.error:
            logger.info(f"      Error: {p.error}")

    logs_path = Path(logs_dir) if logs_dir else Path("logs")
    logs_path.mkdir(exist_ok=True)
    report_path = logs_path / f"faq_report_{timestamp}.json"

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    logger.info(f"Report saved: {report_path}")
    return report


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
        help="Client name (loads configs/{NAME}.json)",
    )
    parser.add_argument("--base-url", type=str, help="Override base URL")

    args = parser.parse_args()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    logger = setup_logging(timestamp, logger_name="auto_faq", log_prefix="auto_faq")

    logger.info("ANYLIVE FAQ AUTOMATION")
    logger.info("=" * 70)

    if args.setup:
        await setup_login(
            logger,
            login_url=FAQ_LOGIN_URL,
            browser_data_subdir=FAQ_BROWSER_DATA,
            session_filename=FAQ_SESSION_FILE,
        )
        return

    if not is_session_valid(FAQ_SESSION_FILE):
        logger.error("No FAQ session found. Please run with --setup first.")
        logger.info("   python auto_faq.py --setup")
        return

    # Resolve config path
    config_path: str
    if args.client:
        config_path = f"configs/{args.client}.json"
    elif args.config:
        config_path = args.config
    else:
        config_path = "configs/faq_template.json"

    cli_overrides: dict = {}
    if args.base_url:
        cli_overrides["base_url"] = args.base_url
    if args.audio_dir:
        cli_overrides["audio_dir"] = args.audio_dir

    try:
        config = load_faq_config(config_path, cli_overrides if cli_overrides else None)
        logger.info(f"Loaded config: {config_path}")
    except FileNotFoundError as e:
        logger.error(f"{e}")
        return
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        return

    # CSV selection: CLI flag > config.csv > autodetect
    try:
        csv_from_config = None
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                _cfg_raw = json.load(f)
                csv_from_config = _cfg_raw.get("csv")
        except Exception:
            csv_from_config = None

        csv_path = find_csv_file(args.csv or csv_from_config)
    except (FileNotFoundError, ValueError) as e:
        logger.error(f"{e}")
        return

    df = load_csv(csv_path, logger)
    products = parse_faq_csv(df, config, logger)

    if not products:
        logger.error("No products to process")
        return

    # Apply start-product filter (by product number, not index)
    if args.start_product > 1:
        products = [p for p in products if p.product_number >= args.start_product]
        logger.info(f"Starting from product #{args.start_product}")

    if args.limit:
        products = products[: args.limit]
        logger.info(f"Limited to {args.limit} products")

    if args.dry_run:
        logger.info("DRY RUN MODE: Audio upload will be skipped")

    if args.debug:
        logger.info("DEBUG MODE: Browser will stay open after execution")

    automation = FAQAutomation(
        config=config,
        headless=args.headless,
        logger=logger,
        dry_run=args.dry_run,
    )

    try:
        await automation.start_browser()

        # Navigate to Product Q&A page once
        if not await automation.navigate_to_product_qa():
            logger.error("Failed to navigate to Product Q&A page")
            return

        for product in products:
            logger.info("")
            logger.info("=" * 70)
            logger.info(
                f"Product #{product.product_number}: {product.product_name} "
                f"({len(product.rows)} questions)"
            )
            logger.info("=" * 70)
            await automation.process_product(product)

    finally:
        if args.debug:
            logger.info("")
            logger.info("=" * 70)
            logger.info("DEBUG MODE: Browser is open for inspection.")
            logger.info("   Press Enter to close the browser and exit.")
            logger.info("=" * 70)
            input()
        await automation.close()

    generate_faq_report(products, config, timestamp, logger)


if __name__ == "__main__":
    asyncio.run(main())
