#!/usr/bin/env python3
import asyncio
import argparse
import json
import logging
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Callable

import pandas as pd
from playwright.async_api import async_playwright, Page, BrowserContext

# Re-export shared utilities so menubar_gui.py and other callers that
# import from auto_tts continue to work without changes.
from shared import (  # noqa: F401
    set_app_support_dir,
    get_session_file_path,
    get_browser_data_dir,
    EmojiFormatter,
    CallbackLogHandler,
    setup_logging,
    find_csv_file,
    load_csv,
    is_session_valid,
    setup_login,
)
from shared import (
    DEFAULT_TIMEOUT,
    CLICK_TIMEOUT,
    NAVIGATION_TIMEOUT,
    POST_AUTOSAVE_DELAY_SECONDS,
    PRE_FILL_START_DELAY_SECONDS,
)

SELECTORS = {
    "add_version_btn": [
        # New UI uses "Add Version" on Live Assets page
        'button:has-text("Add Version")',
        # legacy
        'button:has-text("Add New Version")',
        'text="+ Add New Version"',
        '[class*="add"] button',
    ],
    "version_name_input": [
        # Modal field: placeholder is "Enter Live Asset Name"
        'input[placeholder*="Live Asset Name"]',
        'input[placeholder*="Enter Live Asset Name"]',
        # fallback
        'input[placeholder*="Script Name"]',
        'input[placeholder*="Version Name"]',
        '[role="dialog"] input[type="text"]',
        '[class*="modal"] input[type="text"]',
    ],
    "version_dropdown": [
        # New UI: this is a combobox (role=combobox) under "Copy From Version".
        # Use dialog-scoped selectors so we don't click other comboboxes on the page.
        'dialog:has-text("Create New Version") [role="combobox"]',
        'dialog:has-text("Create New Version") [aria-haspopup="listbox"]',
        # fallback
        'button:has-text("Copy From Version")',
        'text="Select Version"',
        '[role="combobox"]',
        "select",
    ],
    "save_changes_btn": [
        'button:has-text("Save Changes")',
        # safer modal-scoped fallback
        '[role="dialog"] button:has-text("Save")',
        '[class*="modal"] button:has-text("Save")',
        'button[type="submit"]',
    ],
    "voice_clone_dropdown": [
        'button[placeholder="Select Voice Clone"]',
        'button:has-text("Select Voice Clone")',
        '[role="combobox"]',
    ],
    "product_name_input": [
        'input[placeholder*="Product Name"]',
        '[class*="product"] input',
    ],
    "selling_point_textarea": [
        '[class*="selling"] textarea',
        'textarea[placeholder*="Selling"]',
    ],
    "edit_script_tab": [
        'button:has-text("Edit Script")',
        '[role="tab"]:has-text("Edit Script")',
        'a:has-text("Edit Script")',
        '[aria-controls*="edit-script"]',
        '[data-state*="edit-script"]',
    ],
    "generate_speech_btn": [
        # New UI may keep the label, but we also support a few likely variants.
        'button:has-text("Generate Speech")',
        'button:has-text("Generate")',
        'button:has-text("Generate Audio")',
        'button:has-text("Generate TTS")',
        '[class*="generate"] button',
        # fallback to common aria-label
        'button[aria-label*="Generate"]',
    ],
    "save_btn": [
        # Edit page appears to auto-save; no explicit Save button. Keep selectors for legacy UI.
        'button[type="button"]:has-text("Save")',
        'button:has-text("Save")',
    ],
    "template_field": [
        'input[name*="generatedScript"][name*="title"]',
        'input[aria-label="Section Title"]',
        'input[placeholder*="Introduction"]',
    ],
}


@dataclass
class ClientConfig:
    base_url: str
    version_template: str
    voice_name: str
    max_scripts_per_version: int
    enable_voice_selection: bool
    enable_product_info: bool
    csv_columns: dict
    # Optional default CSV file (can be overridden by --csv)
    csv: str = ""


def load_config(config_path: str, cli_overrides: Optional[dict] = None) -> ClientConfig:
    """Load client config JSON.

    Note: We allow an optional top-level `csv` field (path to CSV) so users can
    pin the default input file in configs/default.json.
    """
    if not os.path.exists(config_path):
        raise FileNotFoundError(
            f"Config file not found: {config_path}\n"
            f"Please create a config file or use the template at configs/template.json"
        )

    with open(config_path, "r", encoding="utf-8") as f:
        config_data = json.load(f)

    if cli_overrides:
        config_data.update(cli_overrides)

    return ClientConfig(**config_data)


@dataclass
class ScriptRow:
    product_number: str
    product_name: str
    script_content: str
    audio_code: str
    row_number: int


@dataclass
class Version:
    name: str
    products: List[str]
    scripts: List[str]
    audio_codes: List[str]
    product_number: str = ""
    version_suffix: Optional[str] = None
    success: bool = False
    error: Optional[str] = None
    failed_slots: List[int] = field(default_factory=list)


@dataclass
class Report:
    timestamp: str
    config: dict
    total: int
    successful: int
    failed: int
    versions: List[dict] = field(default_factory=list)


def parse_csv_data(
    df: pd.DataFrame,
    config: ClientConfig,
    logger: logging.Logger,
    flat_mode: bool = False,
) -> List[Version]:
    col_product_no = config.csv_columns.get("product_number", "No")
    col_product_name = config.csv_columns.get("product_name", "Product Name")
    col_script = config.csv_columns.get("script_content", "TH Script")
    col_audio = config.csv_columns.get("audio_code", "Audio Code")

    # Check if pandas already parsed the correct headers (the normal case when
    # the CSV has a proper header row at row 0).
    required_cols = {col_product_no, col_product_name, col_script, col_audio}
    actual_cols = set(str(c).strip() for c in df.columns)

    if required_cols.issubset(actual_cols):
        # Headers are already correct — nothing to do.
        logger.debug(f"CSV headers already parsed correctly: {list(df.columns)}")
    else:
        # Pandas may have mis-parsed an extra metadata row as the header.
        # Check if the first data row actually contains the expected column names
        # and, if so, promote it to be the real header.
        first_row_values = [str(v).strip() for v in df.iloc[0] if pd.notna(v)]
        first_row_set = set(first_row_values)

        header_in_first_row = required_cols.issubset(first_row_set) or any(
            v.lower()
            in {col_product_name.lower(), "product name", "th version", "th script"}
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

    df = df[df[col_product_name] != col_product_name]
    df = df[~df[col_script].str.contains("TH Version", na=False, case=False)]

    df[col_product_name] = df[col_product_name].replace("", pd.NA)
    df[col_product_name] = df[col_product_name].ffill()

    df[col_product_no] = df[col_product_no].replace("", pd.NA)
    df[col_product_no] = df[col_product_no].ffill()

    valid_rows = df[df[col_script].notna() | df[col_audio].notna()]
    logger.info(f"Valid rows: {len(valid_rows)}")

    script_rows: List[ScriptRow] = []
    for idx, row in valid_rows.iterrows():
        raw_number = (
            str(row[col_product_no]).strip() if pd.notna(row[col_product_no]) else "XX"
        )

        try:
            num_value = float(raw_number)
            product_number = f"{int(num_value):02d}"
        except ValueError:
            product_number = raw_number

        product_name = (
            str(row[col_product_name]).strip()
            if pd.notna(row[col_product_name])
            else ""
        )
        script_rows.append(
            ScriptRow(
                product_number=product_number,
                product_name=product_name,
                script_content=(
                    str(row[col_script]).strip() if pd.notna(row[col_script]) else ""
                ),
                audio_code=(
                    str(row[col_audio]).strip() if pd.notna(row[col_audio]) else ""
                ),
                row_number=int(idx) + 2,
            )
        )

    logger.info(f"Total script rows: {len(script_rows)}")

    from collections import defaultdict

    product_groups = defaultdict(list)
    for row in script_rows:
        key = (row.product_number, row.product_name)
        product_groups[key].append(row)

    logger.info(f"Found {len(product_groups)} unique products")

    def sanitize_product_name(name: str) -> str:
        import re

        # Include Thai Unicode range (U+0E00-U+0E7F) to preserve combining
        # characters such as tone marks (่ ้ ๊ ๋) and vowel marks (ิ ี ึ ื ุ ู ั)
        sanitized = re.sub(r"[^\w\s\u0E00-\u0E7F-]", "", name)
        sanitized = re.sub(r"\s+", "_", sanitized)
        return sanitized

    versions: List[Version] = []

    if flat_mode:
        # Flat mode: ignore product boundaries, pack all rows sequentially
        # into fixed-size batches of max_scripts_per_version.
        batch_size = config.max_scripts_per_version
        logger.info(
            f"📦 FLAT MODE: grouping all {len(script_rows)} scripts into batches of {batch_size}"
        )
        for chunk_idx in range(0, len(script_rows), batch_size):
            chunk = script_rows[chunk_idx : chunk_idx + batch_size]
            batch_number = chunk_idx // batch_size + 1
            version_name = f"batch_{batch_number:02d}"

            scripts = [row.script_content for row in chunk]
            audio_codes = [row.audio_code for row in chunk]
            product_names = list(
                dict.fromkeys(row.product_name for row in chunk)
            )  # ordered-unique

            versions.append(
                Version(
                    name=version_name,
                    products=product_names,
                    scripts=scripts,
                    audio_codes=audio_codes,
                    product_number="",
                )
            )

            logger.debug(
                f"Created flat version: {version_name} with {len(scripts)} scripts"
            )
    else:
        for (product_number, product_name), rows in product_groups.items():
            sanitized_name = sanitize_product_name(product_name)

            for chunk_idx in range(0, len(rows), config.max_scripts_per_version):
                chunk = rows[chunk_idx : chunk_idx + config.max_scripts_per_version]
                chunk_number = chunk_idx // config.max_scripts_per_version

                if chunk_number == 0:
                    version_name = f"{product_number}_{sanitized_name}"
                else:
                    version_name = (
                        f"{product_number}_{sanitized_name}_v{chunk_number + 1}"
                    )

                scripts = [row.script_content for row in chunk]
                audio_codes = [row.audio_code for row in chunk]

                versions.append(
                    Version(
                        name=version_name,
                        products=[product_name],
                        scripts=scripts,
                        audio_codes=audio_codes,
                        product_number=product_number,
                        version_suffix=(
                            f"_v{chunk_number + 1}" if chunk_number > 0 else None
                        ),
                    )
                )

                logger.debug(
                    f"Created version: {version_name} with {len(scripts)} scripts"
                )

    logger.info(f"Created {len(versions)} versions total")
    return versions


class TTSAutomation:
    def __init__(
        self,
        config: ClientConfig,
        headless: bool,
        logger: logging.Logger,
        dry_run: bool = False,
        screenshots_dir: Optional[str] = None,
    ):
        self.config = config
        self.headless = headless
        self.logger = logger
        self.dry_run = dry_run
        self.screenshots_dir = screenshots_dir if screenshots_dir else "screenshots"
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.playwright = None

    async def start_browser(self):
        self.logger.info(
            f"PLAYWRIGHT_BROWSERS_PATH={os.environ.get('PLAYWRIGHT_BROWSERS_PATH')}"
        )
        self.playwright = await async_playwright().start()

        # Always use persistent context for consistent session management
        self.logger.info("🌐 Initializing browser with persistent context...")
        user_data_dir = get_browser_data_dir()
        os.makedirs(user_data_dir, exist_ok=True)
        self.context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=self.headless,
            accept_downloads=True,
            # Some macOS environments crash Chromium at launch (SIGTRAP / NotificationCenter).
            # These flags are known to improve stability for this app.
            args=[
                "--start-maximized",
                "--disable-web-security",
                "--disable-features=VizDisplayCompositor",
            ],
        )
        # launch_persistent_context auto-opens one blank tab — reuse it.
        self.page = (
            self.context.pages[0]
            if self.context.pages
            else await self.context.new_page()
        )
        self.page.set_default_timeout(DEFAULT_TIMEOUT)

        session_file = get_session_file_path()
        if is_session_valid():
            self.logger.info("📦 Using saved session from browser_data directory")

            if not await self.validate_session():
                await self.close()
                raise Exception(
                    "Session expired or invalid. Please run setup again:\n"
                    "  python auto_tts.py --setup"
                )

            self.logger.info("✅ Session is valid and authenticated")
        else:
            self.logger.error("❌ No session found. Please run setup first:")
            self.logger.error("  python auto_tts.py --setup")
            raise Exception("No session file found")

    async def close(self):
        if self.context:
            await self.context.close()
        if self.playwright:
            await self.playwright.stop()

    async def validate_session(self) -> bool:
        try:
            self.logger.debug("Validating session...")
            await self.page.goto(
                self.config.base_url, wait_until="networkidle", timeout=30000
            )

            current_url = self.page.url
            if "login" in current_url.lower():
                self.logger.error("❌ Session expired - redirected to login page")
                return False

            self.logger.debug("✓ Session validated successfully")
            return True
        except Exception as e:
            self.logger.error(f"❌ Session validation failed: {e}")
            return False

    async def safe_click(
        self,
        selector_key: str,
        description: str,
        timeout: int = CLICK_TIMEOUT,
        force: bool = False,
    ) -> bool:
        selectors = SELECTORS.get(selector_key, [selector_key])
        for selector in selectors:
            try:
                # wait for visible state specifically to avoid waiting for attached but hidden elements
                element = await self.page.wait_for_selector(
                    selector, timeout=timeout, state="visible"
                )
                if element:
                    await element.click(force=force)
                    self.logger.debug(
                        f"Clicked {description} with selector: {selector}"
                    )
                    return True
            except Exception:
                continue
        self.logger.error(f"Failed to click {description}")
        return False

    async def safe_fill(self, selector_key: str, value: str, description: str) -> bool:
        selectors = SELECTORS.get(selector_key, [selector_key])
        for selector in selectors:
            try:
                element = await self.page.wait_for_selector(
                    selector, timeout=CLICK_TIMEOUT
                )
                if element:
                    await element.fill(value)
                    self.logger.debug(f"Filled {description} with selector: {selector}")
                    return True
            except Exception:
                continue
        self.logger.error(f"Failed to fill {description}")
        return False

    async def take_screenshot(self, version_name: str):
        screenshots_dir = Path(self.screenshots_dir)
        screenshots_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = screenshots_dir / f"error_{version_name}_{timestamp}.png"
        await self.page.screenshot(path=str(path))
        self.logger.info(f"📸 Screenshot saved: {path}")

    async def js_click(self, text: str) -> bool:
        """Click an element containing text using pure JavaScript for maximum speed."""
        try:
            return await self.page.evaluate(
                """(text) => {
                    // Try exact button first
                    const buttons = Array.from(document.querySelectorAll('button'));
                    const target = buttons.find(b => b.innerText.includes(text));
                    if (target) {
                        target.click();
                        return true;
                    }
                    // Fallback to role=tab
                    const tabs = Array.from(document.querySelectorAll('[role="tab"]'));
                    const targetTab = tabs.find(t => t.innerText.includes(text));
                    if (targetTab) {
                        targetTab.click();
                        return true;
                    }
                    return false;
                }""",
                text,
            )
        except Exception as e:
            self.logger.debug(f"JS click failed: {e}")
            return False

    async def is_edit_script_tab_selected(self) -> bool:
        """Return True when the Edit Script tab is currently selected."""
        try:
            return await self.page.evaluate(
                """() => {
                const candidates = Array.from(document.querySelectorAll('button,[role="tab"],a'));
                const edit = candidates.find(el => ((el.innerText || '').toLowerCase()).includes('edit script'));
                if (!edit) return false;
                return edit.getAttribute('aria-selected') === 'true' ||
                       edit.getAttribute('data-headlessui-state') === 'selected' ||
                       edit.getAttribute('data-selected') !== null ||
                       edit.getAttribute('aria-current') === 'page';
            }"""
            )
        except Exception:
            return False

    async def ensure_edit_script_tab_active(
        self, timeout_seconds: float = 6.0, log_info: bool = False
    ) -> bool:
        """Aggressively switch to Edit Script tab as soon as it becomes available."""
        start = asyncio.get_event_loop().time()

        async def _click_edit_script_once() -> bool:
            # Fast JS path: case-insensitive text match across buttons/tabs/links.
            try:
                clicked = await self.page.evaluate(
                    """() => {
                    const candidates = Array.from(document.querySelectorAll('button,[role="tab"],a'));
                    const edit = candidates.find(el => ((el.innerText || '').toLowerCase()).includes('edit script'));
                    if (edit) { edit.click(); return true; }

                    // Fallback: if "Provide Live ..." tab is selected, click the next tab.
                    const tabs = Array.from(document.querySelectorAll('[role="tab"],button'));
                    const provideIdx = tabs.findIndex(el => {
                        const txt = (el.innerText || '').toLowerCase();
                        const selected =
                            el.getAttribute('aria-selected') === 'true' ||
                            el.getAttribute('data-headlessui-state') === 'selected' ||
                            el.getAttribute('data-selected') !== null;
                        return selected && txt.includes('provide live');
                    });
                    if (provideIdx >= 0 && tabs[provideIdx + 1]) {
                        tabs[provideIdx + 1].click();
                        return true;
                    }
                    return false;
                }"""
                )
                if clicked:
                    return True
            except Exception:
                pass

            # Selector path without blocking waits.
            for selector in SELECTORS.get("edit_script_tab", []):
                try:
                    el = await self.page.query_selector(selector)
                    if not el:
                        continue
                    try:
                        if not await el.is_visible():
                            continue
                    except Exception:
                        pass
                    await el.click(force=True)
                    return True
                except Exception:
                    continue
            return False

        while (asyncio.get_event_loop().time() - start) < timeout_seconds:
            if await self.is_edit_script_tab_selected():
                return True

            clicked = await _click_edit_script_once()
            if clicked:
                await asyncio.sleep(0.08)
                if await self.is_edit_script_tab_selected():
                    return True

            await asyncio.sleep(0.08)

        if log_info:
            self.logger.warning(
                "Could not confirm 'Edit Script' tab is active within timeout."
            )
        return await self.is_edit_script_tab_selected()

    async def clear_and_fill(self, element, value: str, max_retries: int = 5) -> bool:
        """Robust fill helper for reactive UIs.

        AnyLive uses controlled inputs; .fill() may not commit.
        Strategy per attempt: fill/type -> verify -> JS -> verify -> clipboard paste -> verify.
        """

        async def _clipboard_paste(el, val: str) -> bool:
            # Write clipboard (best-effort) then paste.
            try:
                await self.page.evaluate(
                    """async (text) => {
                        try { await navigator.clipboard.writeText(text); return true; }
                        catch (e) { return false; }
                    }""",
                    val,
                )
            except Exception:
                pass
            try:
                await el.scroll_into_view_if_needed()
                await el.click(force=True)
                await asyncio.sleep(0.03)
                await el.press("Meta+A")
                await el.press("Backspace")
                await self.page.keyboard.press("Meta+V")
                await asyncio.sleep(0.03)
                try:
                    await el.press("Tab")
                except Exception:
                    pass
                await asyncio.sleep(0.03)
                v = await el.input_value()
                return v is not None and v.strip() == val.strip()
            except Exception:
                return False

        for attempt in range(max_retries):
            try:
                await element.scroll_into_view_if_needed()
                await asyncio.sleep(0.05)
                await element.wait_for_element_state("visible", timeout=5000)
                await element.wait_for_element_state("enabled", timeout=5000)

                await element.click(force=True)
                await asyncio.sleep(0.03)

                try:
                    await element.press("Meta+A")
                    await element.press("Backspace")
                except Exception:
                    try:
                        await element.fill("")
                    except Exception:
                        pass

                # Fill fast
                try:
                    await element.fill(value)
                except Exception:
                    try:
                        await element.type(value, delay=1)
                    except Exception:
                        pass

                await asyncio.sleep(0.03)

                try:
                    actual_value = await element.input_value()
                except Exception:
                    actual_value = None

                if actual_value is not None and actual_value.strip() == value.strip():
                    try:
                        await element.press("Tab")
                    except Exception:
                        pass
                    return True

                # JS fallback
                try:
                    await element.evaluate(
                        """(el, val) => {
                            el.focus();
                            el.value = val;
                            el.dispatchEvent(new Event('input', { bubbles: true }));
                            el.dispatchEvent(new Event('change', { bubbles: true }));
                        }""",
                        value,
                    )
                    await asyncio.sleep(0.05)
                    actual_value2 = await element.input_value()
                    if (
                        actual_value2 is not None
                        and actual_value2.strip() == value.strip()
                    ):
                        try:
                            await element.press("Tab")
                        except Exception:
                            pass
                        return True
                except Exception:
                    pass

                # Clipboard paste fallback (most reliable)
                if await _clipboard_paste(element, value):
                    return True

                self.logger.debug(
                    f"Attempt {attempt + 1}: expected '{value}', got '{(actual_value or '').strip()}'"
                )
            except Exception as e:
                self.logger.debug(
                    f"clear_and_fill attempt {attempt + 1}/{max_retries} failed: {e}"
                )

            await asyncio.sleep(0.12)

        self.logger.warning(
            f"clear_and_fill failed after {max_retries} attempts for value: {value}"
        )
        return False

    async def validate_slot_fields(
        self, slot_index: int, expected_title: str, expected_content: str
    ) -> tuple[bool, str]:
        slot_num = slot_index + 1
        self.logger.debug(f"Validating slot {slot_num} fields...")

        try:
            title_selector = f'input[aria-label="Section Title"] >> nth={slot_index}'
            content_selector = (
                f'textarea[aria-label="Section Content"] >> nth={slot_index}'
            )

            title_input = await self.page.wait_for_selector(
                title_selector, timeout=5000
            )
            content_textarea = await self.page.wait_for_selector(
                content_selector, timeout=5000
            )

            if not title_input or not content_textarea:
                error_msg = f"Slot {slot_num}: Could not find form fields"
                return False, error_msg

            title_value = await title_input.input_value()
            content_value = await content_textarea.input_value()

            title_filled = title_value and title_value.strip()
            content_filled = content_value and content_value.strip()

            if not title_filled and not content_filled:
                error_msg = f"Slot {slot_num}: Both Section Title and Section Content are empty (at least one required)"
                return False, error_msg

            self.logger.debug(
                f"Slot {slot_num} validation passed (title: {'✓' if title_filled else '✗'}, content: {'✓' if content_filled else '✗'})"
            )
            return True, ""

        except Exception as e:
            error_msg = f"Slot {slot_num}: Validation error - {e}"
            return False, error_msg

    async def select_template_from_dropdown(self) -> bool:
        """Select the "Copy From Version" value in the Create New Version dialog.

        This dropdown is flaky: sometimes it opens with "No results found" until reopened.
        We retry open/search/select a few times before failing.
        """
        try:
            dialog = self.page.get_by_role("dialog", name="Create New Version")
            dropdown = dialog.locator(
                '[aria-haspopup="listbox"], [role="combobox"], button:has-text("Select a version to copy from")'
            ).first

            async def open_dropdown() -> None:
                try:
                    await dropdown.click(timeout=CLICK_TIMEOUT)
                except Exception:
                    await dropdown.click(timeout=CLICK_TIMEOUT, force=True)

            for attempt in range(4):
                await open_dropdown()
                await asyncio.sleep(0.12)

                # Always search template name (long lists require filtering).
                searched = False
                try:
                    # Dropdown popover may render outside the dialog (portal), so use page scope.
                    search = self.page.locator(
                        'input[placeholder*="Search"]:visible'
                    ).last
                    if await search.count() > 0:
                        await search.click(timeout=1200)
                        await search.fill("")
                        await search.type(self.config.version_template, delay=10)
                        searched = True
                        await asyncio.sleep(0.2)
                except Exception:
                    searched = False

                # Wait for either options OR the "No results" empty state.
                try:
                    await self.page.wait_for_selector(
                        '[role="option"], text="No results found"', timeout=3000
                    )
                except Exception:
                    pass

                # If popover shows empty state, close and retry.
                try:
                    nr = self.page.locator('text="No results found"')
                    if await nr.count() > 0 and await nr.first.is_visible():
                        raise Exception("No results found")
                except Exception:
                    try:
                        await self.page.keyboard.press("Escape")
                    except Exception:
                        pass
                    await asyncio.sleep(0.4)
                    continue

                # If no options at all, it's also a failure (don't proceed).
                try:
                    if await self.page.locator('[role="option"]').count() == 0:
                        raise Exception("No options")
                except Exception:
                    try:
                        await self.page.keyboard.press("Escape")
                    except Exception:
                        pass
                    await asyncio.sleep(0.4)
                    continue

                # Prefer role-based option.
                opt = self.page.get_by_role(
                    "option", name=self.config.version_template, exact=True
                )
                if await opt.count() > 0:
                    await opt.first.click()
                    self.logger.debug(
                        f"Selected template: {self.config.version_template}"
                    )
                    return True

                # Non-exact option text fallback
                try:
                    opt2 = self.page.get_by_role(
                        "option", name=self.config.version_template
                    )
                    if await opt2.count() > 0:
                        await opt2.first.click()
                        self.logger.debug(
                            f"Selected template (after search): {self.config.version_template}"
                        )
                        return True

                    cand = self.page.locator(
                        f'[role="option"]:has-text("{self.config.version_template}")'
                    )
                    if await cand.count() > 0:
                        await cand.first.click(timeout=2000)
                        self.logger.debug(
                            f"Selected template by text: {self.config.version_template}"
                        )
                        return True
                except Exception:
                    pass

                # If search box was unavailable on this attempt, try reopening once next loop.
                if not searched:
                    self.logger.debug(
                        "Template search input not available; retrying dropdown open."
                    )

                # Close popover before retry loop
                try:
                    await self.page.keyboard.press("Escape")
                except Exception:
                    pass
                await asyncio.sleep(0.3)

            self.logger.error(
                f"Could not find template in dropdown after retries: {self.config.version_template}"
            )
            return False
        except Exception as e:
            self.logger.error(f"Failed to select template: {e}")
            return False

    async def select_voice_from_dropdown(self) -> bool:
        try:
            await self.page.wait_for_selector('[role="option"]', timeout=CLICK_TIMEOUT)
            options = await self.page.query_selector_all('[role="option"]')
            for option in options:
                text = await option.inner_text()
                if text.strip() == self.config.voice_name:
                    await option.click()
                    self.logger.debug(f"Selected exact match: {self.config.voice_name}")
                    return True
            self.logger.error(
                f"Could not find exact match for {self.config.voice_name}"
            )
            return False
        except Exception as e:
            self.logger.error(f"Failed to select voice: {e}")
            return False

    async def wait_for_form_ready(self, expected_count: int, timeout: int = 30) -> bool:
        self.logger.info(f"Waiting for {expected_count} form fields to load...")

        # Optimize: Check if fields are ALREADY visible (due to ?tab=edit-script)
        # If so, return immediately without clicking anything.
        template_selector = 'input[aria-label="Section Title"]'
        script_selector = 'textarea[aria-label="Section Content"]'

        # First attempt right away. If tab appears later, we keep retrying in the loop below.
        if await self.is_edit_script_tab_selected():
            self.logger.info(
                "'Edit Script' tab already selected. Proceeding to stability check."
            )
        else:
            self.logger.info("'Edit Script' tab NOT selected. Clicking immediately...")
            await self.ensure_edit_script_tab_active(timeout_seconds=1.8)

        await asyncio.sleep(0.2)

        template_count = 0
        script_count = 0

        # Stability check loop: Wait for fields to appear and count to stabilize
        # This prevents waiting 30s if the template has fewer slots than expected (e.g. 5 vs 10).
        last_count = 0
        stable_iterations = 0
        REQUIRED_STABLE_ITERATIONS = 3
        POLL_INTERVAL_SECONDS = 0.25
        TAB_RETRY_INTERVAL_SECONDS = 0.8
        last_tab_switch_time = 0.0

        start_time = asyncio.get_event_loop().time()

        while (asyncio.get_event_loop().time() - start_time) < timeout:
            try:
                template_inputs = await self.page.query_selector_all(template_selector)
                script_textareas = await self.page.query_selector_all(script_selector)

                current_count = len(template_inputs)
                script_count = len(script_textareas)

                self.logger.debug(
                    f"Found {current_count} template inputs, {script_count} script textareas"
                )

                if current_count > 0 and current_count == script_count:
                    if current_count == last_count:
                        stable_iterations += 1
                    else:
                        stable_iterations = 0
                        last_count = current_count

                    # If we hit expected count, we can return immediately
                    if current_count >= expected_count:
                        self.logger.info(
                            f"Form ready: Found expected {current_count} slots."
                        )
                        return True

                    # If stable for enough time, proceed even if < expected
                    if stable_iterations >= REQUIRED_STABLE_ITERATIONS:
                        self.logger.info(
                            f"Form ready: Count stabilized at {current_count} slots (Expected {expected_count}). Proceeding."
                        )
                        return True
                else:
                    stable_iterations = 0
                    now = asyncio.get_event_loop().time()
                    if (now - last_tab_switch_time) >= TAB_RETRY_INTERVAL_SECONDS:
                        switched = await self.ensure_edit_script_tab_active(
                            timeout_seconds=1.0
                        )
                        if switched:
                            self.logger.debug(
                                "Switched to 'Edit Script' tab while waiting for fields."
                            )
                        last_tab_switch_time = now

                await asyncio.sleep(POLL_INTERVAL_SECONDS)
            except Exception as e:
                self.logger.debug(f"Error checking form fields: {e}")
                await asyncio.sleep(POLL_INTERVAL_SECONDS)

        self.logger.warning(
            f"Timeout. Proceeding with {last_count} slots (Expected {expected_count})."
        )
        return last_count > 0

    async def navigate_to_scripts(self):
        """Navigate to the Live Asset versions list page.

        New AnyLive UI:
        - versions list: /live-assets/<assetId>?page=1
        - edit page:     /live-assets/<assetId>/edit/<versionId>?tab=edit-script

        We always want the list page before creating a new version.
        """
        current_url = self.page.url

        base = self.config.base_url.split("?")[0].rstrip("/")
        self.logger.info(f"🌐 Navigating to {base}?page=1")

        target = f"{base}?page=1"

        # If already on the list page for this asset, do nothing.
        if current_url.startswith(base) and ("/edit/" not in current_url):
            return

        await self.page.goto(
            target, wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT
        )

        # Sometimes AnyLive keeps you on /edit even after a goto due to SPA routing.
        # Force list page by clicking the sidebar "Live Assets" if still on edit.
        try:
            if "/edit/" in self.page.url:
                await self.page.get_by_role("link", name="Live Assets").click(
                    timeout=8000
                )
                await self.page.wait_for_load_state("domcontentloaded")
                await self.page.goto(
                    target, wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT
                )
        except Exception:
            pass

        # Wait for Add Version button to confirm list page is ready.
        try:
            await self.page.get_by_role("button", name="Add Version").wait_for(
                state="visible", timeout=15000
            )
        except Exception:
            pass

    async def create_new_version(self, name: str) -> bool:
        self.logger.info(f"📝 Creating version: {name}")

        # Always ensure we're on the versions list page before trying to create.
        await self.navigate_to_scripts()

        # Close any stray dialogs/overlays that might be left open.
        try:
            await self.page.keyboard.press("Escape")
        except Exception:
            pass

        # Ensure list page is interactive, then click Add Version with role-based locator.
        add_btn = self.page.get_by_role("button", name="Add Version")
        for attempt in range(3):
            try:
                # Ensure list page really loaded
                await self.page.get_by_role("button", name="Add Version").wait_for(
                    state="visible", timeout=15000
                )
                await add_btn.scroll_into_view_if_needed()
                await add_btn.click(timeout=8000, force=True)
                break
            except Exception as e:
                if attempt == 2:
                    self.logger.error("Failed to click Add Version")
                    self.logger.debug(f"Add Version click error: {e}")
                    return False
                try:
                    await self.page.keyboard.press("Escape")
                except Exception:
                    pass
                try:
                    await self.page.reload(wait_until="domcontentloaded")
                except Exception:
                    pass
                await asyncio.sleep(0.8)

        await asyncio.sleep(0.3)

        if not await self.safe_fill("version_name_input", name, "Version Name input"):
            return False

        # Copy From Version combobox → select template (modal/dropdown is flaky; retry the whole modal flow)
        selected = await self.select_template_from_dropdown()
        if not selected:
            # Close modal and retry once (full restart of modal state)
            try:
                await self.page.keyboard.press("Escape")
            except Exception:
                pass
            await asyncio.sleep(0.4)

            # If modal still visible, click Cancel.
            try:
                cancel_btn = self.page.get_by_role("button", name="Cancel")
                if await cancel_btn.count() > 0:
                    await cancel_btn.first.click(timeout=2000)
            except Exception:
                pass
            await asyncio.sleep(0.3)

            # Re-open Add Version
            add_btn = self.page.get_by_role("button", name="Add Version")
            try:
                await add_btn.click(timeout=8000, force=True)
            except Exception:
                return False

            if not await self.safe_fill(
                "version_name_input", name, "Version Name input"
            ):
                return False

            selected = await self.select_template_from_dropdown()
            if not selected:
                return False

        # Confirm we actually selected something (placeholder should disappear)
        try:
            await self.page.wait_for_selector(
                'text="Copy From Version is required"', state="hidden", timeout=1500
            )
        except Exception:
            pass

        await asyncio.sleep(0.1)

        if not await self.safe_click("save_changes_btn", "Save Changes button"):
            return False

        # optimized: networkidle can hang; rely on explicit element waits instead
        await asyncio.sleep(0.1)

        # Wait for modal overlay to fully disappear (it can intercept clicks).
        try:
            await self.page.wait_for_selector(
                'dialog:has-text("Create New Version")', state="hidden", timeout=1500
            )
        except Exception:
            pass

        # Try to activate Edit Script immediately in case we already landed on edit page.
        if "/edit/" in self.page.url:
            await self.ensure_edit_script_tab_active(timeout_seconds=1.2)

        on_edit_page = "/edit/" in self.page.url
        if not on_edit_page:
            # Some accounts auto-redirect to edit page; others stay on list page with a new row.
            # Poll both conditions and proceed on whichever appears first.
            switched_to_edit = False
            wait_start = asyncio.get_event_loop().time()
            while (asyncio.get_event_loop().time() - wait_start) < 3.0:
                if "/edit/" in self.page.url:
                    await self.ensure_edit_script_tab_active(timeout_seconds=1.0)
                    switched_to_edit = True
                    break

                try:
                    # If form fields are already present, we are effectively on edit surface.
                    title_fields = await self.page.query_selector_all(
                        'input[aria-label="Section Title"]'
                    )
                    if len(title_fields) > 0:
                        await self.ensure_edit_script_tab_active(timeout_seconds=0.8)
                        switched_to_edit = True
                        break

                    link = await self.page.query_selector(f'a:has-text("{name}")')
                    if link:
                        href = await link.get_attribute("href")
                        if href and href.startswith("/"):
                            await self.page.goto(
                                f"https://app.anylive.jp{href}?tab=edit-script",
                                wait_until="domcontentloaded",
                                timeout=NAVIGATION_TIMEOUT,
                            )
                            await self.ensure_edit_script_tab_active(
                                timeout_seconds=1.0
                            )
                            switched_to_edit = True
                            break
                        elif href:
                            await self.page.goto(
                                href,
                                wait_until="domcontentloaded",
                                timeout=NAVIGATION_TIMEOUT,
                            )
                            await self.ensure_edit_script_tab_active(
                                timeout_seconds=1.0
                            )
                            switched_to_edit = True
                            break
                except Exception:
                    pass

                await asyncio.sleep(0.08)

            if not switched_to_edit:
                self.logger.warning(
                    "Created version but could not auto-open edit page quickly."
                )

        # New UI often lands on "Provide Live Knowledge" first. Switch to Edit Script immediately.
        await self.ensure_edit_script_tab_active(timeout_seconds=1.2)

        self.logger.info(f"Created: {name}")
        return True

    async def open_version(self, name: str) -> bool:
        self.logger.info(f"📂 Opening: {name}")
        try:
            row_selector = f'tr:has-text("{name}")'
            row = await self.page.wait_for_selector(row_selector, timeout=CLICK_TIMEOUT)
            if row:
                await row.click()
                await self.page.wait_for_load_state("networkidle")
                return True
        except Exception as e:
            self.logger.error(f"Failed to open version: {e}")
        return False

    async def select_voice_clone(self) -> bool:
        self.logger.info(f"🎙️ Selecting voice: {self.config.voice_name}")

        if not await self.safe_click("voice_clone_dropdown", "Voice Clone dropdown"):
            return False

        await asyncio.sleep(0.3)

        if not await self.select_voice_from_dropdown():
            return False

        await asyncio.sleep(0.3)
        return True

    async def fill_script_slots(self, scripts: List[str]) -> int:
        self.logger.info(f"Filling {len(scripts)} script textareas...")

        filled = 0

        try:
            await self.page.wait_for_selector(
                'textarea[aria-label="Section Content"]', timeout=CLICK_TIMEOUT
            )
            textareas = await self.page.query_selector_all(
                'textarea[aria-label="Section Content"]'
            )
            textarea_count = len(textareas)
            self.logger.info(f"Found {textarea_count} script textareas in DOM")

            if textarea_count < len(scripts):
                self.logger.warning(
                    f"Expected {len(scripts)} script textareas, but found only {textarea_count}"
                )
        except Exception as e:
            self.logger.error(f"Failed to find script textareas: {e}")
            return 0

        for i, script in enumerate(scripts):
            if i < len(textareas):
                self.logger.info(f"Filling script slot {i+1}/{len(scripts)}...")
                if await self.clear_and_fill(textareas[i], script):
                    filled += 1
                    self.logger.info(f"Successfully filled script slot {i+1}")
                else:
                    self.logger.error(f"Failed to fill script slot {i+1}")
                await asyncio.sleep(0.1)

        self.logger.info(f"Filled {filled}/{len(scripts)} script slots")
        return filled

    async def fill_template_fields(self, audio_codes: List[str]) -> int:
        self.logger.info(
            f"Filling {len(audio_codes)} template fields with audio codes..."
        )

        filled = 0

        try:
            await self.page.wait_for_selector(
                'input[aria-label="Section Title"]', timeout=CLICK_TIMEOUT
            )
            template_inputs = await self.page.query_selector_all(
                'input[aria-label="Section Title"]'
            )
            input_count = len(template_inputs)
            self.logger.info(f"Found {input_count} template inputs in DOM")

            if input_count < len(audio_codes):
                self.logger.warning(
                    f"Expected {len(audio_codes)} template inputs, but found only {input_count}"
                )
        except Exception as e:
            self.logger.error(f"Failed to find template inputs: {e}")
            return 0

        for i, audio_code in enumerate(audio_codes):
            if i < len(template_inputs) and audio_code:
                self.logger.info(
                    f"Filling template field {i+1}/{len(audio_codes)} with: {audio_code}"
                )
                if await self.clear_and_fill(template_inputs[i], audio_code):
                    filled += 1
                    self.logger.info(f"Successfully filled template field {i+1}")
                else:
                    self.logger.error(f"Failed to fill template field {i+1}")
                await asyncio.sleep(0.1)

        self.logger.info(f"Filled {filled}/{len(audio_codes)} template fields")
        return filled

    async def fill_product_info(self) -> bool:
        try:
            await self.safe_fill("product_name_input", "-", "Product Name input")
            await self.safe_fill(
                "selling_point_textarea", "-", "Selling Point textarea"
            )
            return True
        except Exception as e:
            self.logger.warning(f"⚠️ Could not fill product info: {e}")
            return True

    async def trigger_generate_speech(self, count: int) -> int:
        self.logger.info("🔊 Clicking Generate Speech buttons...")

        triggered = 0
        buttons = await self.page.query_selector_all(
            ",".join(
                SELECTORS.get(
                    "generate_speech_btn", ['button:has-text("Generate Speech")']
                )
            )
        )

        for i, button in enumerate(buttons[:count]):
            try:
                await button.click()
                triggered += 1
                await asyncio.sleep(0.2)
            except Exception as e:
                self.logger.debug(f"Failed to click Generate Speech {i+1}: {e}")

        self.logger.info(f"Triggered {triggered} generations")
        return triggered

    async def fill_and_generate_slot(
        self, slot_index: int, audio_code: str, script: str, dry_run: bool = False
    ) -> bool:
        slot_num = slot_index + 1
        self.logger.info(f"Processing slot {slot_num}: {audio_code}")

        try:
            # Card-scoped locators (avoid hidden/duplicate inputs from virtualization)
            card = self.page.locator('div:has(button:has-text("Generate Speech"))').nth(
                slot_index
            )

            template = None
            try:
                name_sel = f'input[name="generatedScript.{slot_index}.title"]'
                if await card.locator(name_sel).count() > 0:
                    template = card.locator(name_sel).first
            except Exception:
                template = None

            if template is None:
                template = await self.page.wait_for_selector(
                    f'input[aria-label="Section Title"] >> nth={slot_index}',
                    timeout=CLICK_TIMEOUT,
                )

            async def _type_commit(el, val: str) -> bool:
                try:
                    await el.scroll_into_view_if_needed()
                    await el.click(force=True)
                    await asyncio.sleep(0.02)
                    await el.press("Meta+A")
                    await el.press("Backspace")
                    await self.page.keyboard.type(val, delay=1)
                    # commit
                    try:
                        await el.press("Enter")
                    except Exception:
                        pass
                    try:
                        await el.press("Tab")
                    except Exception:
                        pass
                    await asyncio.sleep(0.05)
                    v = (await el.input_value()).strip()
                    return v == val.strip()
                except Exception:
                    return False

            ok_title = await _type_commit(template, audio_code)
            if not ok_title:
                # retry with clear_and_fill + keyboard commit
                try:
                    ok_title = await self.clear_and_fill(template, audio_code)
                    if not ok_title:
                        ok_title = await _type_commit(template, audio_code)
                except Exception:
                    ok_title = False

            if not ok_title:
                self.logger.error(f"Failed to fill template for slot {slot_num}")
                return False

            textarea = None
            # try:
            #     name_sel = f'textarea[name="generatedScript.{slot_index}.content"]'
            #     if await card.locator(name_sel).count() > 0:
            #         textarea = card.locator(name_sel).first
            # except Exception:
            #     textarea = None

            if textarea is None:
                textarea = await self.page.wait_for_selector(
                    f'textarea[aria-label="Section Content"] >> nth={slot_index}',
                    timeout=CLICK_TIMEOUT,
                )

            async def _type_long_text(el, val: str) -> bool:
                """Last-resort for long Thai scripts: real typing tends to commit in controlled textareas."""
                try:
                    await el.scroll_into_view_if_needed()
                    await el.click(force=True)
                    await asyncio.sleep(0.02)
                    await el.press("Meta+A")
                    await el.press("Backspace")
                    await self.page.keyboard.type(val, delay=1)
                    await asyncio.sleep(0.03)
                    try:
                        await el.press("Tab")
                    except Exception:
                        pass
                    await asyncio.sleep(0.05)
                    v = await el.input_value()
                    return v is not None and v.strip() == val.strip()
                except Exception:
                    return False

            ok_script = await self.clear_and_fill(textarea, script)

            # Special-case slot 1 long script: if it didn't stick, try typing.
            if (not ok_script) and slot_index == 0 and len(script.strip()) > 150:
                ok_script = await _type_long_text(textarea, script)

            if not ok_script:
                # If the textarea is in a weird controlled state, try a fresh locator once.
                try:
                    # Re-click Edit Script (sometimes focus/virtualization breaks the first textarea)
                    try:
                        await self.safe_click(
                            "edit_script_tab", "Edit Script tab", timeout=5000
                        )
                        await asyncio.sleep(0.2)
                    except Exception:
                        pass

                    if slot_index == 0:
                        try:
                            await self.page.evaluate("window.scrollTo(0, 0)")
                            await asyncio.sleep(0.1)
                        except Exception:
                            pass

                    textarea2 = self.page.locator(
                        'textarea[aria-label="Section Content"]'
                    ).nth(slot_index)
                    await textarea2.scroll_into_view_if_needed()
                    await textarea2.click(force=True)

                    ok2 = await self.clear_and_fill(textarea2, script)
                    if (not ok2) and slot_index == 0 and len(script.strip()) > 150:
                        ok2 = await _type_long_text(textarea2, script)

                    if not ok2:
                        self.logger.error(f"Failed to fill script for slot {slot_num}")
                        return False

                    textarea = textarea2
                except Exception:
                    self.logger.error(f"Failed to fill script for slot {slot_num}")
                    return False

            # Hard verification: ensure values actually stuck in DOM AND in the visible card.
            try:
                tv = (await template.input_value()).strip()
                sv = (await textarea.input_value()).strip()

                async def _card_visible_text(idx: int) -> tuple[str, str]:
                    """Return (titleText, bodyText) from the rendered card.

                    Prefer reading from name-based fields (generatedScript.{i}.title/content)
                    because those reflect the actual controlled form state.
                    """
                    title_txt = ""
                    body_txt = ""
                    try:
                        t = self.page.locator(
                            f'input[name="generatedScript.{idx}.title"]'
                        ).first
                        title_txt = (await t.input_value()).strip()
                    except Exception:
                        title_txt = ""
                    try:
                        s = self.page.locator(
                            f'textarea[name="generatedScript.{idx}.content"]'
                        ).first
                        body_txt = (await s.input_value()).strip()
                    except Exception:
                        body_txt = ""
                    return title_txt, body_txt

                if audio_code.strip() and tv != audio_code.strip():
                    try:
                        await template.scroll_into_view_if_needed()
                        await template.click(force=True)
                        await template.press("Meta+A")
                        await template.press("Backspace")
                        await self.page.keyboard.type(audio_code, delay=1)
                        await template.press("Enter")
                        await template.press("Tab")
                        await asyncio.sleep(0.05)
                        tv2 = (await template.input_value()).strip()
                        if tv2 != audio_code.strip():
                            self.logger.warning(
                                f"Slot {slot_num} title mismatch after retry (expected '{audio_code.strip()}', got '{tv2}')"
                            )
                            return False
                    except Exception:
                        self.logger.warning(
                            f"Slot {slot_num} title mismatch after fill (expected '{audio_code.strip()}', got '{tv}')"
                        )
                        return False

                if script.strip() and sv != script.strip():
                    if slot_index == 0:
                        # Keep slot 1 reliable, but avoid multi-pass full re-typing that can duplicate content.
                        ok_slot1_retry = await self.clear_and_fill(textarea, script)
                        if (not ok_slot1_retry) and len(script.strip()) > 150:
                            ok_slot1_retry = await _type_long_text(textarea, script)

                        if not ok_slot1_retry:
                            self.logger.warning(
                                f"Slot {slot_num} script mismatch after retry"
                            )
                            return False

                        sv2 = (await textarea.input_value() or "").strip()
                        if sv2 != script.strip():
                            self.logger.warning(
                                f"Slot {slot_num} script mismatch after retry"
                            )
                            return False
                    else:
                        self.logger.warning(
                            f"Slot {slot_num} script mismatch after fill"
                        )
                        return False
            except Exception:
                pass

            await asyncio.sleep(0.2)

            validation_passed, validation_error = await self.validate_slot_fields(
                slot_index, audio_code, script
            )
            if not validation_passed:
                self.logger.warning(
                    f"Slot {slot_num} validation failed: {validation_error}"
                )
                self.logger.warning(
                    f"Skipping Generate Speech for slot {slot_num} due to empty fields"
                )
                return False

            if not dry_run:
                button_clicked = False

                await asyncio.sleep(0.3)

                template_selector = (
                    f'input[aria-label="Section Title"] >> nth={slot_index}'
                )
                template_fresh = await self.page.wait_for_selector(
                    template_selector, timeout=5000
                )

                try:
                    parent_container = await template_fresh.evaluate_handle(
                        "(el) => { let p = el; for(let i=0; i<6; i++) { if(p.parentElement) p = p.parentElement; } return p; }"
                    )

                    if parent_container:
                        button = await parent_container.query_selector(
                            ",".join(
                                SELECTORS.get(
                                    "generate_speech_btn",
                                    ['button:has-text("Generate Speech")'],
                                )
                            )
                        )
                        if button:
                            await button.scroll_into_view_if_needed()
                            await asyncio.sleep(0.2)
                            await button.click()
                            self.logger.debug(
                                f"Clicked Generate Speech for slot {slot_num} via parent container"
                            )
                            await asyncio.sleep(0.3)
                            button_clicked = True
                except Exception as e:
                    self.logger.debug(
                        f"Parent container approach failed for slot {slot_num}: {e}"
                    )

                if not button_clicked:
                    try:
                        self.logger.debug(
                            f"Falling back to nth-index approach for slot {slot_num}"
                        )
                        # Match any "Generate" variant, then pick nth.
                        gen_selectors = ",".join(
                            SELECTORS.get(
                                "generate_speech_btn",
                                ['button:has-text("Generate Speech")'],
                            )
                        )
                        button_selector = f"({gen_selectors}) >> nth={slot_index}"
                        button = await self.page.wait_for_selector(
                            button_selector, timeout=5000
                        )

                        if button:
                            await button.scroll_into_view_if_needed()
                            await asyncio.sleep(0.2)
                            await button.click()
                            self.logger.debug(
                                f"Clicked Generate Speech for slot {slot_num} via nth-index fallback"
                            )
                            await asyncio.sleep(0.3)
                            button_clicked = True
                        else:
                            self.logger.warning(
                                f"Generate Speech button not found for slot {slot_num}"
                            )
                    except Exception as e:
                        self.logger.warning(
                            f"Failed to click Generate Speech for slot {slot_num}: {e}"
                        )

            self.logger.info(f"Completed slot {slot_num}")
            return True

        except Exception as e:
            self.logger.error(f"Error processing slot {slot_num}: {e}")
            return False

    async def validate_form_fields(self, expected_count: int) -> tuple[bool, str]:
        self.logger.info("🔍 Validating form fields before save...")

        try:
            title_selector = 'input[aria-label="Section Title"]'
            content_selector = 'textarea[aria-label="Section Content"]'

            title_inputs = await self.page.query_selector_all(title_selector)
            content_textareas = await self.page.query_selector_all(content_selector)

            title_count = len(title_inputs)
            content_count = len(content_textareas)

            self.logger.debug(
                f"Found {title_count} title fields, {content_count} content fields"
            )

            if title_count < expected_count or content_count < expected_count:
                error_msg = f"Template has insufficient fields: expected at least {expected_count}, found {title_count} titles and {content_count} contents"
                self.logger.error(error_msg)
                return False, error_msg

            if title_count > expected_count or content_count > expected_count:
                self.logger.debug(
                    f"Template has {title_count} slots, using first {expected_count} for this version"
                )

            empty_titles = []
            empty_contents = []

            for i in range(min(expected_count, len(title_inputs))):
                try:
                    value = await title_inputs[i].input_value()
                    if not value or not value.strip():
                        empty_titles.append(i + 1)
                        self.logger.warning(f"Section Title slot {i + 1} is empty")
                except Exception as e:
                    self.logger.debug(f"Error checking title slot {i + 1}: {e}")
                    empty_titles.append(i + 1)

            for i in range(min(expected_count, len(content_textareas))):
                try:
                    value = await content_textareas[i].input_value()
                    if not value or not value.strip():
                        empty_contents.append(i + 1)
                        self.logger.warning(f"Section Content slot {i + 1} is empty")
                except Exception as e:
                    self.logger.debug(f"Error checking content slot {i + 1}: {e}")
                    empty_contents.append(i + 1)

            if empty_titles or empty_contents:
                error_parts = []
                if empty_titles:
                    error_parts.append(
                        f"Missing Section Title in slots: {empty_titles}"
                    )
                if empty_contents:
                    error_parts.append(
                        f"Missing Section Content in slots: {empty_contents}"
                    )
                error_msg = " and ".join(error_parts)
                self.logger.error(error_msg)
                return False, error_msg

            self.logger.info(f"✓ All {expected_count} slots validated successfully")
            return True, ""

        except Exception as e:
            error_msg = f"Validation error: {e}"
            self.logger.error(error_msg)
            return False, error_msg

    async def save_version(self, expected_slots: int) -> bool:

        self.logger.debug("Waiting for form state to stabilize...")
        await asyncio.sleep(0.1)

        try:
            await self.page.evaluate("document.activeElement?.blur()")
        except Exception:
            pass

        validation_passed, error_msg = await self.validate_form_fields(expected_slots)
        if not validation_passed:
            self.logger.error(f"❌ Validation failed: {error_msg}")
            return False

        # Wait for auto-save to complete
        self.logger.info("💾 Waiting for auto-save...")
        try:
            # Fast path: if already auto-saved, return immediately.
            await self.page.wait_for_selector('text="Auto Saved"', timeout=250)
            self.logger.info("✅ Auto-saved successfully")
        except Exception:
            try:
                # If still saving, allow a bit more time for the status to flip.
                saving_visible = False
                for saving_selector in (
                    'text="Saving..."',
                    'text="Saving"',
                    'text="Auto Saving"',
                ):
                    try:
                        loc = self.page.locator(saving_selector)
                        if await loc.count() > 0 and await loc.first.is_visible():
                            saving_visible = True
                            break
                    except Exception:
                        continue

                wait_timeout = 3500 if saving_visible else 1200
                await self.page.wait_for_selector(
                    'text="Auto Saved"', timeout=wait_timeout
                )
                self.logger.info("✅ Auto-saved successfully")
            except Exception as e:
                self.logger.warning(
                    f"Could not confirm auto-save status quickly (continuing): {e}"
                )
                # Continue anyway as the system likely saved

        # Always add a small buffer to avoid racing UI state before clicking Back.
        await asyncio.sleep(POST_AUTOSAVE_DELAY_SECONDS)

        return True

    async def process_version(self, version: Version) -> bool:
        try:
            await self.navigate_to_scripts()

            if not await self.create_new_version(version.name):
                raise Exception("Failed to create version")

            if not await self.wait_for_form_ready(len(version.scripts)):
                raise Exception("Form fields did not load in time")

            if self.config.enable_voice_selection:
                if not await self.select_voice_clone():
                    raise Exception("Failed to select voice")

            if self.config.enable_product_info:
                await self.fill_product_info()

            self.logger.info(f"Processing {len(version.scripts)} slots...")
            # Give the form a brief moment to settle before typing slot 1.
            await asyncio.sleep(PRE_FILL_START_DELAY_SECONDS)
            successful_slots = 0
            failed_slots: list[int] = []
            for i in range(len(version.scripts)):
                audio_code = (
                    version.audio_codes[i] if i < len(version.audio_codes) else ""
                )
                script = version.scripts[i]
                ok = await self.fill_and_generate_slot(
                    i, audio_code, script, dry_run=self.dry_run
                )
                if ok:
                    successful_slots += 1
                else:
                    failed_slots.append(i + 1)

            version.failed_slots = failed_slots
            self.logger.info(
                f"Completed {successful_slots}/{len(version.scripts)} slots"
            )
            if failed_slots:
                self.logger.warning(f"Failed slots: {failed_slots}")

            if successful_slots == 0:
                raise Exception("Failed to fill any slots")

            if not await self.save_version(len(version.scripts)):
                raise Exception("Failed to save version")

            # Go back to versions list using the in-app back button ("<") to avoid SPA state issues.
            try:
                await self.page.get_by_role("button", name="Back").click(timeout=1200)
            except Exception:
                try:
                    await self.page.locator("main button").first.click(timeout=800)
                except Exception:
                    pass

            if failed_slots:
                self.logger.warning(
                    f"PARTIAL SUCCESS: {version.name} (failed slots: {failed_slots})"
                )
            else:
                self.logger.info(f"SUCCESS: {version.name}")

            # Mark success only when all slots succeeded
            version.success = len(failed_slots) == 0
            return version.success

        except Exception as e:
            self.logger.error(f"Failed: {e}")

            try:
                await self.take_screenshot(version.name)
            except Exception as screenshot_error:
                self.logger.warning(f"Failed to take screenshot: {screenshot_error}")

            version.error = str(e)
            self.logger.error(f"❌ FAILED: {version.name} - {e}")
            return False

    async def download_all_versions(self, limit: int = None, replace: bool = False, start_version: int = 1):
        """Download audio files for every version, except the template.

        Workflow:
        1. Collect all version links across all pagination pages.
        2. For each version (except the template):
           a. Navigate into the version's edit page.
           b. Switch to the "Edit Script" tab.
           c. Find all download buttons inside script boxes and click them.
           d. Navigate back to the versions list.
        """
        template_name = (self.config.version_template or "").strip()
        self.logger.info(
            f"⬇️  DOWNLOAD MODE: Downloading all versions (skipping '{template_name}')"
        )
        if template_name and len(template_name) < 4:
            self.logger.warning(
                "⚠️ version_template is very short ('%s'); use a distinctive template name to avoid accidental skips.",
                template_name,
            )

        # Set up downloads directory.
        downloads_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "downloads"
        )
        os.makedirs(downloads_dir, exist_ok=True)
        self.logger.info(f"📁 Downloads will be saved to: {downloads_dir}")

        base = self.config.base_url.split("?")[0].rstrip("/")

        # --- Phase 1: Collect all version links across all pages ---
        all_versions = []  # list of (name, href) tuples
        page_num = 1

        while True:
            target = f"{base}?page={page_num}"
            self.logger.info(f"📄 Scanning page {page_num} for versions...")
            await self.page.goto(
                target, wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT
            )

            # Wait for the page content to render.
            try:
                await self.page.wait_for_selector(
                    'a[href*="/live-assets/"]', timeout=10000
                )
            except Exception:
                pass
            await asyncio.sleep(0.5)

            # Extract version links via JavaScript.
            versions_on_page = await self.page.evaluate(
                """() => {
                const links = Array.from(document.querySelectorAll('a'));
                return links
                    .filter(a => a.href && a.href.includes('/live-assets/') && a.href.includes('/edit/'))
                    .map(a => ({ name: a.innerText.trim(), href: a.href }));
            }"""
            )

            if not versions_on_page:
                if page_num == 1:
                    self.logger.warning("No version links found on page 1.")
                else:
                    self.logger.info(f"No versions on page {page_num}, done scanning.")
                break

            for v in versions_on_page:
                all_versions.append((v["name"], v["href"]))

            self.logger.info(
                f"  Found {len(versions_on_page)} versions on page {page_num}"
            )

            # Check for next page button.
            has_next = await self.page.evaluate(
                """() => {
                const btn = document.querySelector('button[aria-label="Next page"]');
                if (!btn) return false;
                return !btn.disabled && btn.getAttribute('aria-disabled') !== 'true';
            }"""
            )

            if has_next:
                page_num += 1
            else:
                self.logger.info(f"Last page reached (page {page_num}).")
                break

        # Sort versions numerically by the leading number in the version name
        # (e.g. "01_...", "06_...", "13_...") so downloads proceed in order.
        import re as _re

        def _version_sort_key(item):
            name = item[0]
            m = _re.match(r"^(\d+)", name)
            return (int(m.group(1)) if m else float("inf"), name)

        all_versions.sort(key=_version_sort_key)
        self.logger.info(f"Total versions found: {len(all_versions)}")

        # Apply start_version offset (1-indexed)
        if start_version > 1:
            all_versions = all_versions[start_version - 1:]
            self.logger.info(f"Starting from version #{start_version} (skipping first {start_version - 1})")

        # --- Phase 2: Visit each version and download ---
        total_downloaded = 0
        total_skipped = 0
        versions_processed = 0

        for version_name, version_href in all_versions:
            # Intentionally skip the template baseline (blank/unfilled script).
            # This relies on `version_template` being a distinctive identifier.
            if template_name and template_name in version_name:
                self.logger.debug(f"Skipping template: {version_name}")
                total_skipped += 1
                continue

            # Apply limit if set
            if limit and versions_processed >= limit:
                self.logger.info(f"Reached download limit of {limit}, stopping.")
                break

            versions_processed += 1
            self.logger.info("")
            self.logger.info(f"[{versions_processed}] Opening: {version_name}")

            try:
                # Navigate to the version edit page.
                await self.page.goto(
                    version_href,
                    wait_until="domcontentloaded",
                    timeout=NAVIGATION_TIMEOUT,
                )
                await asyncio.sleep(1.0)

                # Click the Edit Script tab explicitly (URL param not reliable in SPA).
                try:
                    await self.page.click("text=Edit Script", timeout=5000)
                except Exception:
                    # Fallback: try JS click
                    await self.page.evaluate(
                        """() => {
                        const tabs = Array.from(document.querySelectorAll('button, a'));
                        const tab = tabs.find(t => t.textContent.trim() === 'Edit Script');
                        if (tab) tab.click();
                    }"""
                    )

                # Wait for script boxes to appear (div.group elements).
                try:
                    await self.page.wait_for_selector("div.group", timeout=8000)
                except Exception:
                    self.logger.warning(
                        f"  Script boxes did not load for: {version_name}"
                    )
                    continue

                await asyncio.sleep(0.5)

                # Create downloads directory for this version.
                safe_name = version_name.replace("/", "_").replace("\\", "_")[:100]
                version_dl_dir = os.path.join(downloads_dir, safe_name)
                os.makedirs(version_dl_dir, exist_ok=True)

                # Count download buttons via JS.
                # The new "Export" button shares the same SVG icon (M4 15.204) as
                # the per-row download buttons, but has visible innerText "Export".
                # Real download buttons are icon-only (empty innerText), so we skip
                # any button whose trimmed innerText is non-empty to exclude Export.
                btn_count = await self.page.evaluate(
                    """() => {
                    let count = 0;
                    const buttons = Array.from(document.querySelectorAll('button'));
                    for (const btn of buttons) {
                        // Skip buttons with visible text (e.g. the new "Export" button)
                        if (btn.innerText.trim() !== '') continue;
                        const paths = Array.from(btn.querySelectorAll('svg path'));
                        for (const p of paths) {
                            const d = p.getAttribute('d') || '';
                            if (d.startsWith('M4 15.204')) {
                                btn.setAttribute('data-dl-idx', count);
                                count++;
                                break;
                            }
                        }
                    }
                    return count;
                }"""
                )

                if btn_count == 0:
                    self.logger.warning(
                        f"  No download buttons found in: {version_name}"
                    )
                    continue

                # Click each download button individually with expect_download.
                version_dl_count = 0
                for idx in range(btn_count):
                    try:
                        async with self.page.expect_download(timeout=15000) as dl_info:
                            await self.page.evaluate(
                                f"""() => {{
                                const btn = document.querySelector('button[data-dl-idx="{idx}"]');
                                if (btn) btn.click();
                            }}"""
                            )
                        download = await dl_info.value
                        filename = download.suggested_filename or f"audio_{idx+1}.mp3"
                        save_path = os.path.join(version_dl_dir, filename)
                        if os.path.exists(save_path) and not replace:
                            self.logger.info(
                                f"  ⏭️  Already exists, skipping: {filename}"
                            )
                            await download.cancel()
                            continue
                        await download.save_as(save_path)
                        self.logger.info(f"  ⬇️  Saved: {filename}")
                        version_dl_count += 1
                    except Exception as e:
                        self.logger.warning(f"  Failed to download button {idx+1}: {e}")

                total_downloaded += version_dl_count

            except Exception as e:
                self.logger.warning(f"  Error processing {version_name}: {e}")

            # Brief pause between versions.
            await asyncio.sleep(0.3)

        self.logger.info("")
        self.logger.info("=" * 70)
        self.logger.info(
            f"⬇️  DOWNLOAD COMPLETE: {total_downloaded} files from {versions_processed} versions"
        )
        self.logger.info(f"   Skipped: {total_skipped} (template)")
        self.logger.info("=" * 70)
        return total_downloaded


def print_version_info(version: Version, logger: logging.Logger):
    logger.info("")
    logger.info("=" * 70)
    logger.info(f"{version.name} - {len(version.scripts)} scripts")
    if version.products:
        logger.info(
            f"   Products: {', '.join(version.products[:3])}{'...' if len(version.products) > 3 else ''}"
        )
    logger.info("=" * 70)


def generate_report(
    versions: List[Version],
    config: ClientConfig,
    timestamp: str,
    logger: logging.Logger,
    logs_dir: Optional[str] = None,
) -> Report:
    successful = sum(1 for v in versions if v.success)
    partial = sum(1 for v in versions if getattr(v, "failed_slots", None))
    failed = len(versions) - successful

    report = Report(
        timestamp=datetime.now().isoformat(),
        config={
            "grouping_strategy": "product_based",
            "max_scripts_per_version": config.max_scripts_per_version,
        },
        total=len(versions),
        successful=successful,
        failed=failed,
        versions=[
            {
                "version": v.name,
                "product_number": v.product_number,
                "products": v.products,
                "scripts": len(v.scripts),
                "success": v.success,
                "failed_slots": v.failed_slots,
                "error": v.error,
            }
            for v in versions
        ],
    )

    logger.info("")
    logger.info("=" * 70)
    logger.info("📋 FINAL REPORT")
    logger.info("=" * 70)
    logger.info("")
    logger.info(
        f"Total: {report.total} | Success: {successful} ✅ | Partial: {partial} ⚠️ | Failed: {failed} ❌"
    )
    logger.info("")
    logger.info("📑 VERSION → PRODUCTS MAPPING:")
    logger.info("-" * 70)

    for v in versions:
        status = "OK" if v.success else "FAILED"
        logger.info(f"{status} {v.name}: {len(v.scripts)} scripts")
        if v.error:
            logger.info(f"      Error: {v.error}")
        logger.info("")

    if logs_dir is None:
        logs_dir = Path("logs")
    else:
        logs_dir = Path(logs_dir)
    logs_dir.mkdir(exist_ok=True)
    report_path = logs_dir / f"report_{timestamp}.json"

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(asdict(report), f, ensure_ascii=False, indent=2)

    logger.info(f"📄 Report saved: {report_path}")
    return report


async def run_job(
    config_path: str,
    csv_path: str,
    *,
    headless: bool = False,
    dry_run: bool = False,
    debug: bool = False,
    download: bool = False,
    replace: bool = False,
    start_version: int = 1,
    limit: Optional[int] = None,
    app_support_dir: Optional[str] = None,
    log_callback: Optional[Callable[[str], None]] = None,
    debug_callback: Optional[Callable[[], None]] = None,
) -> dict:
    """
    Main automation job function for GUI and programmatic execution.

    Args:
        config_path: Path to client config JSON file
        csv_path: Path to CSV file with scripts
        headless: Run browser in headless mode
        dry_run: Skip Generate Speech button clicks

        debug: Keep browser open after execution
        start_version: Starting version number (1-indexed)
        limit: Limit number of versions to process
        app_support_dir: Directory for logs, screenshots, session (default: current dir)
        log_callback: Optional callback for streaming logs to GUI
        debug_callback: Optional callback for debug mode (instead of blocking input)

    Returns:
        dict with keys: success (bool), report (Report), error (Optional[str])
    """
    # Set up app support directory if provided
    if app_support_dir:
        set_app_support_dir(app_support_dir)
        logs_dir = os.path.join(app_support_dir, "logs")
        screenshots_dir = os.path.join(app_support_dir, "screenshots")
    else:
        logs_dir = None
        screenshots_dir = None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    logger = setup_logging(timestamp, logs_dir=logs_dir, log_callback=log_callback)

    logger.info("🚀 ANYLIVE TTS AUTOMATION")
    logger.info("=" * 70)

    try:
        # Load configuration
        if not os.path.exists(config_path):
            error_msg = f"Config file not found: {config_path}"
            logger.error(f"❌ {error_msg}")
            return {"success": False, "report": None, "error": error_msg}

        config = load_config(config_path)
        logger.info(f"📋 Loaded config: {config_path}")

        # --- Download-only workflow (separate from fill/create) ---
        if download:
            automation = TTSAutomation(
                config=config,
                headless=headless,
                logger=logger,
                screenshots_dir=screenshots_dir,
            )
            try:
                await automation.start_browser()
                count = await automation.download_all_versions(
                    limit=limit, replace=replace
                )
            finally:
                if debug:
                    logger.info("🐛 DEBUG MODE: Leaving browser open for inspection")
                    if debug_callback:
                        debug_callback()
                else:
                    await automation.close()
            return {"success": True, "report": None, "error": None, "downloaded": count}

        # Load and parse CSV
        if not os.path.exists(csv_path):
            error_msg = f"CSV file not found: {csv_path}"
            logger.error(f"❌ {error_msg}")
            return {"success": False, "report": None, "error": error_msg}

        df = load_csv(csv_path, logger)
        versions = parse_csv_data(df, config, logger)

        if not versions:
            error_msg = "No versions to process"
            logger.error(f"❌ {error_msg}")
            return {"success": False, "report": None, "error": error_msg}

        # Apply start_version and limit
        start_idx = start_version - 1
        if start_idx > 0:
            versions = versions[start_idx:]
            logger.info(f"Starting from version {start_version}")

        if limit:
            versions = versions[:limit]
            logger.info(f"Limited to {limit} versions")

        if dry_run:
            logger.info("🔇 DRY RUN MODE: Generate Speech will be skipped")

        if debug:
            logger.info(
                "🐛 DEBUG MODE: Browser will stay open after execution (non-blocking)"
            )

        # Run automation
        automation = TTSAutomation(
            config=config,
            headless=headless,
            logger=logger,
            dry_run=dry_run,
            screenshots_dir=screenshots_dir,
        )

        try:
            await automation.start_browser()

            for version in versions:
                print_version_info(version, logger)
                await automation.process_version(version)

        finally:
            if debug:
                logger.info("")
                logger.info("=" * 70)
                logger.info("🐛 DEBUG MODE: Leaving browser open for inspection")
                logger.info(
                    "   (Automation will not auto-close the browser in debug mode)"
                )
                if debug_callback:
                    debug_callback()
                else:
                    logger.info("   Close the browser manually when you're done.")
                logger.info("=" * 70)
            else:
                await automation.close()

        # Generate report
        report = generate_report(versions, config, timestamp, logger, logs_dir=logs_dir)

        return {"success": True, "report": report, "error": None}

    except Exception as e:
        error_msg = str(e)
        logger.error(f"❌ Job failed: {error_msg}")
        return {"success": False, "report": None, "error": error_msg}


async def main():
    parser = argparse.ArgumentParser(description="AnyLive TTS Automation")
    parser.add_argument("--setup", action="store_true", help="One-time login setup")
    parser.add_argument(
        "--csv", type=str, help="Path to CSV file (auto-detects if not specified)"
    )
    parser.add_argument(
        "--start-version", type=int, default=1, help="Starting version number"
    )
    parser.add_argument("--limit", type=int, help="Limit number of versions to process")
    parser.add_argument(
        "--headless", action="store_true", help="Run browser in headless mode"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Run without clicking Generate Speech"
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Keep browser open after execution for debugging",
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help="Download files for all versions (except template)",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Re-download and replace existing files (use with --download)",
    )
    parser.add_argument(
        "--flat",
        action="store_true",
        help="Flat mode: ignore product boundaries and pack scripts sequentially (N per version, set N with --max-scripts)",
    )

    parser.add_argument("--config", type=str, help="Path to client config JSON file")
    parser.add_argument(
        "--client", type=str, help="Client name (loads configs/{NAME}.json)"
    )
    parser.add_argument("--base-url", type=str, help="Override base URL")
    parser.add_argument("--voice", type=str, help="Override voice clone name")
    parser.add_argument("--template", type=str, help="Override version template name")
    parser.add_argument(
        "--max-scripts", type=int, help="Override max scripts per version"
    )

    args = parser.parse_args()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    logger = setup_logging(timestamp)

    logger.info("🚀 ANYLIVE TTS AUTOMATION")
    logger.info("=" * 70)

    if args.setup:
        await setup_login(logger)
        return

    if not is_session_valid():
        logger.error("❌ No session found. Please run with --setup first.")
        logger.info("   python auto_tts.py --setup")
        return

    # --- Download-only workflow (separate from fill/create) ---
    if args.download:
        config_path = None
        if args.client:
            config_path = f"configs/{args.client}.json"
        elif args.config:
            config_path = args.config
        else:
            config_path = "configs/default.json"

        cli_overrides = {}
        if args.base_url:
            cli_overrides["base_url"] = args.base_url
        if args.template:
            cli_overrides["version_template"] = args.template

        try:
            config = load_config(config_path, cli_overrides if cli_overrides else None)
        except Exception as e:
            logger.error(f"❌ {e}")
            return

        logger.info(f"📋 Loaded config: {config_path}")
        automation = TTSAutomation(config=config, headless=args.headless, logger=logger)

        try:
            await automation.start_browser()
            await automation.download_all_versions(
                limit=args.limit, replace=args.replace, start_version=args.start_version
            )
        finally:
            if args.debug:
                logger.info("🐛 DEBUG MODE: Browser is open for inspection.")
                logger.info("   Press Enter to close the browser and exit.")
                input()
            await automation.close()
        return

    config_path = None
    if args.client:
        config_path = f"configs/{args.client}.json"
    elif args.config:
        config_path = args.config
    else:
        config_path = "configs/default.json"

    cli_overrides = {}
    if args.base_url:
        cli_overrides["base_url"] = args.base_url
    if args.voice:
        cli_overrides["voice_name"] = args.voice
    if args.template:
        cli_overrides["version_template"] = args.template
    if args.max_scripts:
        cli_overrides["max_scripts_per_version"] = args.max_scripts

    try:
        config = load_config(config_path, cli_overrides if cli_overrides else None)
        logger.info(f"📋 Loaded config: {config_path}")
        if cli_overrides:
            logger.debug(f"Applied CLI overrides: {cli_overrides}")
    except FileNotFoundError as e:
        logger.error(f"❌ {e}")
        return
    except Exception as e:
        logger.error(f"❌ Failed to load config: {e}")
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
        logger.error(f"❌ {e}")
        return

    df = load_csv(csv_path, logger)
    versions = parse_csv_data(df, config, logger, flat_mode=args.flat)

    if not versions:
        logger.error("❌ No versions to process")
        return

    start_idx = args.start_version - 1
    if start_idx > 0:
        versions = versions[start_idx:]
        logger.info(f"Starting from version {args.start_version}")

    if args.limit:
        versions = versions[: args.limit]
        logger.info(f"Limited to {args.limit} versions")

    if args.flat:
        logger.info(
            f"📦 FLAT MODE: Scripts packed sequentially, {config.max_scripts_per_version} per version"
        )

    if args.dry_run:
        logger.info("🔇 DRY RUN MODE: Generate Speech will be skipped")

    if args.debug:
        logger.info("🐛 DEBUG MODE: Browser will stay open after execution")

    automation = TTSAutomation(
        config=config, headless=args.headless, logger=logger, dry_run=args.dry_run
    )

    try:
        await automation.start_browser()

        for version in versions:
            print_version_info(version, logger)
            await automation.process_version(version)

    finally:
        if args.debug:
            logger.info("")
            logger.info("=" * 70)
            logger.info("🐛 DEBUG MODE: Browser is open for inspection.")
            logger.info("   Press Enter to close the browser and exit.")
            logger.info("=" * 70)
            input()
        await automation.close()

    generate_report(versions, config, timestamp, logger)


if __name__ == "__main__":
    asyncio.run(main())
