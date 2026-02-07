#!/usr/bin/env python3
import asyncio
import argparse
import glob
import json
import logging
import os
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Callable

import pandas as pd
from playwright.async_api import async_playwright, Page, BrowserContext

# In packaged apps Playwright may default to looking for browsers inside the
# application bundle. Force use of the standard macOS cache directory where
# `python -m playwright install chromium` downloads browsers.
os.environ.setdefault(
    "PLAYWRIGHT_BROWSERS_PATH",
    os.path.join(str(Path.home()), "Library", "Caches", "ms-playwright"),
)

DEFAULT_TIMEOUT = 30000
CLICK_TIMEOUT = 8000
NAVIGATION_TIMEOUT = 45000
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2
SESSION_FILE = "session_state.json"

_app_support_dir = None

def set_app_support_dir(path: Optional[str]):
    global _app_support_dir
    _app_support_dir = path

def get_session_file_path() -> str:
    if _app_support_dir:
        return os.path.join(_app_support_dir, "session_state.json")
    return SESSION_FILE


def get_browser_data_dir() -> str:
    """Return the directory used for Playwright persistent context.

    IMPORTANT: In a packaged macOS .app, the current working directory can be
    unexpected (often '/'), so using a relative path like './browser_data' can
    break silently (no profile/session persisted; permission errors).

    When running in menubar GUI mode we set _app_support_dir, so we store browser
    data under ~/Library/Application Support/AnyLiveTTS/browser_data.
    """
    if _app_support_dir:
        return os.path.join(_app_support_dir, "browser_data")
    return "./browser_data"

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
        'select',
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

    with open(config_path, 'r', encoding='utf-8') as f:
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


class EmojiFormatter(logging.Formatter):
    def format(self, record):
        return f"{self.formatTime(record, '%H:%M:%S')} | {record.levelname} | {record.getMessage()}"


class CallbackLogHandler(logging.Handler):
    def __init__(self, callback: Callable[[str], None]):
        super().__init__()
        self.callback = callback
        self.setFormatter(EmojiFormatter())

    def emit(self, record):
        try:
            msg = self.format(record)
            self.callback(msg)
        except Exception:
            self.handleError(record)


def setup_logging(timestamp: str, logs_dir: Optional[str] = None, log_callback: Optional[Callable[[str], None]] = None) -> logging.Logger:
    if logs_dir is None:
        logs_dir = Path("logs")
    else:
        logs_dir = Path(logs_dir)
    logs_dir.mkdir(exist_ok=True)

    logger = logging.getLogger("auto_tts")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(EmojiFormatter())
    logger.addHandler(console_handler)

    file_handler = logging.FileHandler(logs_dir / f"auto_tts_{timestamp}.log", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    logger.addHandler(file_handler)

    if log_callback:
        callback_handler = CallbackLogHandler(log_callback)
        callback_handler.setLevel(logging.INFO)
        logger.addHandler(callback_handler)

    return logger


def find_csv_file(explicit_path: Optional[str]) -> str:
    if explicit_path:
        if not os.path.exists(explicit_path):
            raise FileNotFoundError(f"CSV file not found: {explicit_path}")
        return explicit_path

    csv_files = glob.glob("*.csv")

    if len(csv_files) == 0:
        raise FileNotFoundError("No CSV file found in project folder")
    elif len(csv_files) == 1:
        return csv_files[0]
    else:
        raise ValueError(f"Multiple CSV files found: {csv_files}. Use --csv to specify.")


def load_csv(path: str, logger: logging.Logger) -> pd.DataFrame:
    logger.info(f"📂 Loading CSV: {path}")
    try:
        df = pd.read_csv(path, encoding="utf-8", header=0)
    except UnicodeDecodeError:
        logger.debug("UTF-8 failed, trying cp874 encoding")
        df = pd.read_csv(path, encoding="cp874", header=0)
    return df


def parse_csv_data(df: pd.DataFrame, config: ClientConfig, logger: logging.Logger) -> List[Version]:
    col_product_no = config.csv_columns.get("product_number", "No")
    col_product_name = config.csv_columns.get("product_name", "Product Name")
    col_script = config.csv_columns.get("script_content", "TH Script")
    col_audio = config.csv_columns.get("audio_code", "Audio Code")

    default_columns = ["No", "Product Name", "Scene", "part", "TH Script", "col_f", "Audio Code", "col_h", "PIC"]

    if len(df.columns) <= len(default_columns):
        header_detected = any(
            str(val).strip().lower() in [col_product_name.lower(), "product name", "th version", "th script"]
            for val in df.iloc[0] if pd.notna(val)
        )

        if not header_detected:
            df.columns = default_columns[:len(df.columns)]

    df = df[df[col_product_name] != col_product_name]
    df = df[~df[col_script].str.contains("TH Version", na=False, case=False)]

    df[col_product_name] = df[col_product_name].replace('', pd.NA)
    df[col_product_name] = df[col_product_name].ffill()

    df[col_product_no] = df[col_product_no].replace('', pd.NA)
    df[col_product_no] = df[col_product_no].ffill()

    valid_rows = df[df[col_script].notna() | df[col_audio].notna()]
    logger.info(f"Valid rows: {len(valid_rows)}")

    script_rows: List[ScriptRow] = []
    for idx, row in valid_rows.iterrows():
        raw_number = str(row[col_product_no]).strip() if pd.notna(row[col_product_no]) else "XX"

        try:
            num_value = float(raw_number)
            product_number = f"{int(num_value):02d}"
        except ValueError:
            product_number = raw_number

        product_name = str(row[col_product_name]).strip() if pd.notna(row[col_product_name]) else ""
        script_rows.append(ScriptRow(
            product_number=product_number,
            product_name=product_name,
            script_content=str(row[col_script]).strip() if pd.notna(row[col_script]) else "",
            audio_code=str(row[col_audio]).strip() if pd.notna(row[col_audio]) else "",
            row_number=int(idx) + 2
        ))

    logger.info(f"Total script rows: {len(script_rows)}")

    from collections import defaultdict
    product_groups = defaultdict(list)
    for row in script_rows:
        key = (row.product_number, row.product_name)
        product_groups[key].append(row)

    logger.info(f"Found {len(product_groups)} unique products")

    def sanitize_product_name(name: str) -> str:
        import re
        sanitized = re.sub(r'[^\w\s-]', '', name)
        sanitized = re.sub(r'\s+', '_', sanitized)
        return sanitized

    versions: List[Version] = []

    for (product_number, product_name), rows in product_groups.items():
        sanitized_name = sanitize_product_name(product_name)

        for chunk_idx in range(0, len(rows), config.max_scripts_per_version):
            chunk = rows[chunk_idx:chunk_idx + config.max_scripts_per_version]
            chunk_number = chunk_idx // config.max_scripts_per_version

            if chunk_number == 0:
                version_name = f"{product_number}_{sanitized_name}"
            else:
                version_name = f"{product_number}_{sanitized_name}_v{chunk_number + 1}"

            scripts = [row.script_content for row in chunk]
            audio_codes = [row.audio_code for row in chunk]

            versions.append(Version(
                name=version_name,
                products=[product_name],
                scripts=scripts,
                audio_codes=audio_codes,
                product_number=product_number,
                version_suffix=f"_v{chunk_number + 1}" if chunk_number > 0 else None
            ))

            logger.debug(f"Created version: {version_name} with {len(scripts)} scripts")

    logger.info(f"Created {len(versions)} versions total")
    return versions


async def setup_login(logger: logging.Logger, gui_mode: bool = False):
    logger.info("🔐 Starting login setup...")
    session_file = get_session_file_path()

    async with async_playwright() as p:
        # Always use persistent context for consistent session management
        logger.info("🌐 Initializing browser with persistent context...")
        logger.info(f"PLAYWRIGHT_BROWSERS_PATH={os.environ.get('PLAYWRIGHT_BROWSERS_PATH')}")
        user_data_dir = get_browser_data_dir()
        logger.info(f"📁 Browser profile dir: {user_data_dir}")
        os.makedirs(user_data_dir, exist_ok=True)

        try:
            context = await p.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                headless=False,
                args=['--start-maximized', '--disable-web-security', '--disable-features=VizDisplayCompositor']
            )
        except Exception as e:
            logger.exception("❌ Failed to launch Chromium persistent context")
            raise

        page = await context.new_page()

        # In GUI mode, always open browser for manual login
        if not gui_mode:
            # Check if existing session exists and try to validate it
            if is_session_valid():
                logger.info(f"📦 Found existing session file: {session_file}")
                logger.info("🔍 Verifying session validity...")

                try:
                    await page.goto("https://app.anylive.jp", wait_until="networkidle", timeout=30000)

                    # Check if we're still logged in (not redirected to login page)
                    current_url = page.url
                    if "login" not in current_url.lower():
                        logger.info("✅ Existing session is still valid!")
                        logger.info("🎉 Setup complete! You can now run without --setup")
                        await context.close()
                        return
                    else:
                        logger.warning("⚠️ Session expired. Need to login again.")
                except Exception as e:
                    logger.warning(f"⚠️ Session validation failed: {e}")
            else:
                logger.info("📭 No existing session found.")
        else:
            logger.info("🌐 GUI mode: Always opening browser for manual login")

        # If we reach here, need manual login
        logger.info("🌐 Opening browser for manual login...")

        await page.goto("https://app.anylive.jp", wait_until="networkidle")
        logger.info("🌐 Navigated to AnyLive. Please log in manually.")

        if not gui_mode:
            input("Press Enter when you have completed login...")
        else:
            # In GUI mode, wait for user to complete login with better feedback
            logger.info("🌐 GUI mode: Please complete login in the browser window...")
            logger.info("🌐 The browser window should open in a new window...")

            # Bring browser to front
            try:
                await page.bring_to_front()
            except:
                pass

            # Wait and check periodically if login is complete
            for i in range(60):  # Wait up to 60 seconds
                await asyncio.sleep(1)
                try:
                    current_url = page.url
                    if "login" not in current_url.lower():
                        logger.info("✅ Login detected automatically!")
                        break
                except:
                    pass

                if i % 10 == 0:  # Every 10 seconds
                    logger.info(f"🌐 Waiting for login... ({60-i}s remaining)")

            # Final check
            current_url = page.url
            if "login" in current_url.lower():
                logger.warning("⚠️ Login timeout. You may need to try again.")

        # Verify login by checking current URL
        current_url = page.url
        logger.info(f"Current URL: {current_url}")

        if "login" in current_url.lower():
            logger.warning("⚠️ Still on login page. Please make sure you're logged in.")
        else:
            logger.info("✅ Login detected!")

        # Save session marker (persistent context auto-saves to browser_data)
        if "login" in current_url.lower():
            logger.warning("⚠️ Not saving session marker because login was not completed")
        else:
            with open(session_file, 'w') as f:
                json.dump({'setup_complete': True, 'timestamp': datetime.now().isoformat()}, f)
            logger.info("✅ Session saved to browser_data directory")
            logger.info(f"✅ Setup marker saved to {session_file}")

        await context.close()

    logger.info("🎉 Setup complete! You can now run without --setup")


def is_session_valid() -> bool:
    session_file = get_session_file_path()
    return os.path.exists(session_file)


class TTSAutomation:
    def __init__(self, config: ClientConfig, headless: bool, logger: logging.Logger, dry_run: bool = False, no_save: bool = False, screenshots_dir: Optional[str] = None):
        self.config = config
        self.headless = headless
        self.logger = logger
        self.dry_run = dry_run
        self.no_save = no_save
        self.screenshots_dir = screenshots_dir if screenshots_dir else "screenshots"
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.playwright = None

    async def start_browser(self):
        self.logger.info(f"PLAYWRIGHT_BROWSERS_PATH={os.environ.get('PLAYWRIGHT_BROWSERS_PATH')}")
        self.playwright = await async_playwright().start()

        # Always use persistent context for consistent session management
        self.logger.info("🌐 Initializing browser with persistent context...")
        user_data_dir = get_browser_data_dir()
        os.makedirs(user_data_dir, exist_ok=True)
        self.context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=self.headless,
            # Some macOS environments crash Chromium at launch (SIGTRAP / NotificationCenter).
            # These flags are known to improve stability for this app.
            args=['--start-maximized', '--disable-web-security', '--disable-features=VizDisplayCompositor']
        )
        self.page = await self.context.new_page()
        self.page.set_default_timeout(DEFAULT_TIMEOUT)

        session_file = get_session_file_path()
        if is_session_valid():
            self.logger.info(f"📦 Using saved session from browser_data directory")

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
            await self.page.goto(self.config.base_url, wait_until="networkidle", timeout=30000)

            current_url = self.page.url
            if "login" in current_url.lower():
                self.logger.error("❌ Session expired - redirected to login page")
                return False

            self.logger.debug("✓ Session validated successfully")
            return True
        except Exception as e:
            self.logger.error(f"❌ Session validation failed: {e}")
            return False

    async def safe_click(self, selector_key: str, description: str) -> bool:
        selectors = SELECTORS.get(selector_key, [selector_key])
        for selector in selectors:
            try:
                element = await self.page.wait_for_selector(selector, timeout=CLICK_TIMEOUT)
                if element:
                    await element.click()
                    self.logger.debug(f"Clicked {description} with selector: {selector}")
                    return True
            except Exception:
                continue
        self.logger.error(f"Failed to click {description}")
        return False

    async def safe_fill(self, selector_key: str, value: str, description: str) -> bool:
        selectors = SELECTORS.get(selector_key, [selector_key])
        for selector in selectors:
            try:
                element = await self.page.wait_for_selector(selector, timeout=CLICK_TIMEOUT)
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
                        '''(el, val) => {
                            el.focus();
                            el.value = val;
                            el.dispatchEvent(new Event('input', { bubbles: true }));
                            el.dispatchEvent(new Event('change', { bubbles: true }));
                        }''',
                        value,
                    )
                    await asyncio.sleep(0.05)
                    actual_value2 = await element.input_value()
                    if actual_value2 is not None and actual_value2.strip() == value.strip():
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

                self.logger.debug(f"Attempt {attempt + 1}: expected '{value}', got '{(actual_value or '').strip()}'")
            except Exception as e:
                self.logger.debug(f"clear_and_fill attempt {attempt + 1}/{max_retries} failed: {e}")

            await asyncio.sleep(0.12)

        self.logger.warning(f"clear_and_fill failed after {max_retries} attempts for value: {value}")
        return False

    async def validate_slot_fields(self, slot_index: int, expected_title: str, expected_content: str) -> tuple[bool, str]:
        slot_num = slot_index + 1
        self.logger.debug(f"Validating slot {slot_num} fields...")

        try:
            title_selector = f'input[aria-label="Section Title"] >> nth={slot_index}'
            content_selector = f'textarea[aria-label="Section Content"] >> nth={slot_index}'

            title_input = await self.page.wait_for_selector(title_selector, timeout=5000)
            content_textarea = await self.page.wait_for_selector(content_selector, timeout=5000)

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

            self.logger.debug(f"Slot {slot_num} validation passed (title: {'✓' if title_filled else '✗'}, content: {'✓' if content_filled else '✗'})")
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
            dropdown = dialog.locator('[aria-haspopup="listbox"], [role="combobox"], button:has-text("Select a version to copy from")').first

            async def open_dropdown() -> None:
                try:
                    await dropdown.click(timeout=CLICK_TIMEOUT)
                except Exception:
                    await dropdown.click(timeout=CLICK_TIMEOUT, force=True)

            for attempt in range(3):
                await open_dropdown()

                # Wait for either options OR the "No results" empty state.
                try:
                    await self.page.wait_for_selector('[role="option"], text="No results found"', timeout=3000)
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
                opt = self.page.get_by_role("option", name=self.config.version_template)
                if await opt.count() > 0:
                    await opt.first.click()
                    self.logger.debug(f"Selected template: {self.config.version_template}")
                    return True

                # Search fallback
                try:
                    search = dialog.get_by_placeholder("Search...")
                    await search.fill("")
                    await search.type(self.config.version_template, delay=10)
                    await asyncio.sleep(0.2)

                    opt2 = self.page.get_by_role("option", name=self.config.version_template)
                    if await opt2.count() > 0:
                        await opt2.first.click()
                        self.logger.debug(f"Selected template (after search): {self.config.version_template}")
                        return True

                    cand = self.page.locator(f'text="{self.config.version_template}"')
                    if await cand.count() > 0:
                        await cand.first.click(timeout=2000)
                        self.logger.debug(f"Selected template by text: {self.config.version_template}")
                        return True
                except Exception:
                    pass

                # Keyboard fallback: select first available option
                try:
                    await open_dropdown()
                    await self.page.keyboard.press("ArrowDown")
                    await self.page.keyboard.press("Enter")
                    self.logger.debug("Selected first template option via keyboard fallback")
                    return True
                except Exception:
                    pass

                # Close popover before retry loop
                try:
                    await self.page.keyboard.press("Escape")
                except Exception:
                    pass
                await asyncio.sleep(0.3)

            self.logger.error(f"Could not find template in dropdown after retries: {self.config.version_template}")
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
            self.logger.error(f"Could not find exact match for {self.config.voice_name}")
            return False
        except Exception as e:
            self.logger.error(f"Failed to select voice: {e}")
            return False

    async def wait_for_form_ready(self, expected_count: int, timeout: int = 30) -> bool:
        self.logger.info(f"Waiting for {expected_count} form fields to load...")

        # New UI: script fields are under the "Edit Script" tab.
        # Optimize: click Edit Script ASAP (don't wait on other tabs like "Provide Live Knowledge").
        try:
            tab = self.page.get_by_role("tab", name="Edit Script")
            await tab.wait_for(state="visible", timeout=8000)
            await tab.click(timeout=8000)
        except Exception:
            # Fallback: try by text in case role mapping changes
            try:
                await self.page.locator('text="Edit Script"').first.click(timeout=8000)
            except Exception:
                pass

        await asyncio.sleep(0.2)

        # Confirmed on current AnyLive UI (Edit Script tab):
        # - input[aria-label="Section Title"] (10)
        # - textarea[aria-label="Section Content"] (10)
        template_selector = 'input[aria-label="Section Title"]'
        script_selector = 'textarea[aria-label="Section Content"]'

        template_count = 0
        script_count = 0

        start_time = asyncio.get_event_loop().time()

        while (asyncio.get_event_loop().time() - start_time) < timeout:
            try:
                template_inputs = await self.page.query_selector_all(template_selector)
                script_textareas = await self.page.query_selector_all(script_selector)

                template_count = len(template_inputs)
                script_count = len(script_textareas)

                self.logger.debug(f"Found {template_count} template inputs, {script_count} script textareas")

                if template_count >= expected_count and script_count >= expected_count:
                    self.logger.info(f"Form ready: {template_count} template inputs, {script_count} script textareas")
                    return True

                await asyncio.sleep(0.5)
            except Exception as e:
                self.logger.debug(f"Error checking form fields: {e}")
                await asyncio.sleep(0.5)

        self.logger.warning(f"Timeout waiting for form fields. Found {template_count}/{expected_count} templates, {script_count}/{expected_count} scripts")
        return False

    async def navigate_to_scripts(self):
        """Navigate to the Live Asset versions list page.

        New AnyLive UI:
        - versions list: /live-assets/<assetId>?page=1
        - edit page:     /live-assets/<assetId>/edit/<versionId>?tab=edit-script

        We always want the list page before creating a new version.
        """
        current_url = self.page.url

        base = self.config.base_url.split('?')[0].rstrip('/')
        self.logger.info(f"🌐 Navigating to {base}?page=1")

        target = f"{base}?page=1"

        # If already on the list page for this asset, do nothing.
        if current_url.startswith(base) and ("/edit/" not in current_url):
            return

        await self.page.goto(target, wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT)

        # Sometimes AnyLive keeps you on /edit even after a goto due to SPA routing.
        # Force list page by clicking the sidebar "Live Assets" if still on edit.
        try:
            if "/edit/" in self.page.url:
                await self.page.get_by_role("link", name="Live Assets").click(timeout=8000)
                await self.page.wait_for_load_state("domcontentloaded")
                await self.page.goto(target, wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT)
        except Exception:
            pass

        # Wait for Add Version button to confirm list page is ready.
        try:
            await self.page.get_by_role("button", name="Add Version").wait_for(state="visible", timeout=15000)
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
                await self.page.get_by_role("button", name="Add Version").wait_for(state="visible", timeout=15000)
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

            if not await self.safe_fill("version_name_input", name, "Version Name input"):
                return False

            selected = await self.select_template_from_dropdown()
            if not selected:
                return False

        # Confirm we actually selected something (placeholder should disappear)
        try:
            await self.page.wait_for_selector('text="Copy From Version is required"', state='hidden', timeout=1500)
        except Exception:
            pass

        await asyncio.sleep(0.1)

        if not await self.safe_click("save_changes_btn", "Save Changes button"):
            return False

        await self.page.wait_for_load_state("networkidle")

        # Wait for modal overlay to fully disappear (it can intercept clicks).
        try:
            await self.page.wait_for_selector('dialog:has-text("Create New Version")', state='hidden', timeout=CLICK_TIMEOUT)
        except Exception:
            pass

        # After creation, open the newly created version edit page.
        try:
            link = await self.page.wait_for_selector(f'a:has-text("{name}")', timeout=30000)
            await link.scroll_into_view_if_needed()
            href = await link.get_attribute('href')
            if href and href.startswith('/'):
                await self.page.goto(f"https://app.anylive.jp{href}?tab=edit-script", wait_until="networkidle", timeout=NAVIGATION_TIMEOUT)
            elif href:
                await self.page.goto(href, wait_until="networkidle", timeout=NAVIGATION_TIMEOUT)
        except Exception as e:
            self.logger.warning(f"Created version but could not open it automatically: {e}")

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
            await self.page.wait_for_selector('textarea[aria-label="Section Content"]', timeout=CLICK_TIMEOUT)
            textareas = await self.page.query_selector_all('textarea[aria-label="Section Content"]')
            textarea_count = len(textareas)
            self.logger.info(f"Found {textarea_count} script textareas in DOM")

            if textarea_count < len(scripts):
                self.logger.warning(f"Expected {len(scripts)} script textareas, but found only {textarea_count}")
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
        self.logger.info(f"Filling {len(audio_codes)} template fields with audio codes...")

        filled = 0

        try:
            await self.page.wait_for_selector('input[aria-label="Section Title"]', timeout=CLICK_TIMEOUT)
            template_inputs = await self.page.query_selector_all('input[aria-label="Section Title"]')
            input_count = len(template_inputs)
            self.logger.info(f"Found {input_count} template inputs in DOM")

            if input_count < len(audio_codes):
                self.logger.warning(f"Expected {len(audio_codes)} template inputs, but found only {input_count}")
        except Exception as e:
            self.logger.error(f"Failed to find template inputs: {e}")
            return 0

        for i, audio_code in enumerate(audio_codes):
            if i < len(template_inputs) and audio_code:
                self.logger.info(f"Filling template field {i+1}/{len(audio_codes)} with: {audio_code}")
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
            await self.safe_fill("selling_point_textarea", "-", "Selling Point textarea")
            return True
        except Exception as e:
            self.logger.warning(f"⚠️ Could not fill product info: {e}")
            return True

    async def trigger_generate_speech(self, count: int) -> int:
        self.logger.info("🔊 Clicking Generate Speech buttons...")

        triggered = 0
        buttons = await self.page.query_selector_all(','.join(SELECTORS.get('generate_speech_btn', ['button:has-text("Generate Speech")'])))

        for i, button in enumerate(buttons[:count]):
            try:
                await button.click()
                triggered += 1
                await asyncio.sleep(0.2)
            except Exception as e:
                self.logger.debug(f"Failed to click Generate Speech {i+1}: {e}")

        self.logger.info(f"Triggered {triggered} generations")
        return triggered

    async def fill_and_generate_slot(self, slot_index: int, audio_code: str, script: str, dry_run: bool = False) -> bool:
        slot_num = slot_index + 1
        self.logger.info(f"Processing slot {slot_num}: {audio_code}")

        try:
            template_selector = f'input[aria-label="Section Title"] >> nth={slot_index}'
            template = await self.page.wait_for_selector(template_selector, timeout=CLICK_TIMEOUT)

            async def _fill_title_with_keyboard(el) -> bool:
                try:
                    await el.scroll_into_view_if_needed()
                    await el.click(force=True)
                    await asyncio.sleep(0.05)
                    await el.press("Meta+A")
                    await el.press("Backspace")
                    # insertText triggers proper input events in many controlled inputs
                    await self.page.keyboard.insert_text(audio_code)
                    await el.press("Tab")
                    await asyncio.sleep(0.05)
                    v = (await el.input_value()).strip()
                    return v == audio_code.strip()
                except Exception:
                    return False

            ok_title = await self.clear_and_fill(template, audio_code)
            if not ok_title:
                # retry with fresh locator + keyboard path (more reliable than fill() for controlled inputs)
                try:
                    template2 = self.page.locator('input[aria-label="Section Title"]').nth(slot_index)
                    if await _fill_title_with_keyboard(template2):
                        template = template2
                        ok_title = True
                    else:
                        ok_title = await self.clear_and_fill(template2, audio_code)
                        if ok_title:
                            template = template2
                except Exception:
                    ok_title = False

            if not ok_title:
                self.logger.error(f"Failed to fill template for slot {slot_num}")
                return False

            script_selector = f'textarea[aria-label="Section Content"] >> nth={slot_index}'
            textarea = await self.page.wait_for_selector(script_selector, timeout=CLICK_TIMEOUT)

            async def _type_long_text(el, val: str) -> bool:
                """Last-resort for long Thai scripts: real typing tends to commit in controlled textareas."""
                try:
                    await el.scroll_into_view_if_needed()
                    await el.click(force=True)
                    await asyncio.sleep(0.03)
                    await el.press("Meta+A")
                    await el.press("Backspace")
                    await self.page.keyboard.type(val, delay=1)
                    await asyncio.sleep(0.05)
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
                        await self.page.get_by_role("tab", name="Edit Script").click(timeout=5000)
                        await asyncio.sleep(0.2)
                    except Exception:
                        pass

                    if slot_index == 0:
                        try:
                            await self.page.evaluate('window.scrollTo(0, 0)')
                            await asyncio.sleep(0.1)
                        except Exception:
                            pass

                    textarea2 = self.page.locator('textarea[aria-label="Section Content"]').nth(slot_index)
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
                    """Return (titleText, bodyText) from the rendered card, not the input values."""
                    # Each paragraph card has a drag handle and a 3-dot menu; title appears as visible text.
                    card = self.page.locator('div:has(button:has-text("Generate Speech"))').nth(idx)
                    title_txt = ""
                    body_txt = ""
                    try:
                        # first line in the card (title)
                        title_txt = (await card.locator('text=/^template_\d+|^SC\d+|^SC\d\d+|^SC\d\d\d+/').first.inner_text()).strip()
                    except Exception:
                        try:
                            # fallback: take first text node-ish
                            title_txt = (await card.inner_text()).splitlines()[0].strip()
                        except Exception:
                            title_txt = ""
                    try:
                        # second line in the card (body) often includes script_1 for defaults
                        lines = (await card.inner_text()).splitlines()
                        if len(lines) > 1:
                            body_txt = lines[1].strip()
                    except Exception:
                        body_txt = ""
                    return title_txt, body_txt

                async def _retry_slot1_commit() -> bool:
                    for _ in range(3):
                        try:
                            await self.page.evaluate('window.scrollTo(0, 0)')
                        except Exception:
                            pass
                        try:
                            await self.page.get_by_role("tab", name="Edit Script").click(timeout=5000)
                        except Exception:
                            pass
                        await asyncio.sleep(0.15)

                        t = self.page.locator('input[aria-label="Section Title"]').nth(0)
                        s = self.page.locator('textarea[aria-label="Section Content"]').nth(0)

                        # Title commit
                        try:
                            await t.click(force=True)
                            await t.press("Meta+A")
                            await t.press("Backspace")
                            await self.page.keyboard.type(audio_code, delay=1)
                            await t.press("Enter")
                            await t.press("Tab")
                        except Exception:
                            pass

                        # Script commit
                        try:
                            await s.click(force=True)
                            await s.press("Meta+A")
                            await s.press("Backspace")
                            await self.page.keyboard.type(script, delay=1)
                            try:
                                await s.press("Tab")
                            except Exception:
                                pass
                        except Exception:
                            pass

                        # click outside to force React commit
                        try:
                            await self.page.locator('body').click(position={"x": 5, "y": 5})
                        except Exception:
                            pass

                        try:
                            await self.page.wait_for_selector('text="Auto Saved"', timeout=4000)
                        except Exception:
                            pass

                        # Verify by VISIBLE card label
                        title_vis, body_vis = await _card_visible_text(0)
                        if (audio_code.strip() and title_vis == audio_code.strip()) and (script.strip() and body_vis != "script_1"):
                            return True
                        await asyncio.sleep(0.2)
                    return False

                if slot_index == 0:
                    title_vis, body_vis = await _card_visible_text(0)
                    if title_vis == "template_1" or body_vis == "script_1":
                        if not await _retry_slot1_commit():
                            self.logger.warning(f"Slot {slot_num} still default in UI after retries (title_vis='{title_vis}', body_vis='{body_vis}')")
                            return False

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
                            self.logger.warning(f"Slot {slot_num} title mismatch after retry (expected '{audio_code.strip()}', got '{tv2}')")
                            return False
                    except Exception:
                        self.logger.warning(f"Slot {slot_num} title mismatch after fill (expected '{audio_code.strip()}', got '{tv}')")
                        return False

                if script.strip() and sv != script.strip():
                    if slot_index == 0:
                        if not await _retry_slot1_commit():
                            self.logger.warning(f"Slot {slot_num} script mismatch after retries")
                            return False
                    else:
                        self.logger.warning(f"Slot {slot_num} script mismatch after fill")
                        return False
            except Exception:
                pass

            await asyncio.sleep(0.2)

            validation_passed, validation_error = await self.validate_slot_fields(slot_index, audio_code, script)
            if not validation_passed:
                self.logger.warning(f"Slot {slot_num} validation failed: {validation_error}")
                self.logger.warning(f"Skipping Generate Speech for slot {slot_num} due to empty fields")
                return False

            if not dry_run:
                button_clicked = False

                await asyncio.sleep(0.3)

                template_fresh = await self.page.wait_for_selector(template_selector, timeout=5000)

                try:
                    parent_container = await template_fresh.evaluate_handle(
                        '(el) => { let p = el; for(let i=0; i<6; i++) { if(p.parentElement) p = p.parentElement; } return p; }'
                    )

                    if parent_container:
                        button = await parent_container.query_selector(','.join(SELECTORS.get('generate_speech_btn', ['button:has-text("Generate Speech")'])))
                        if button:
                            await button.scroll_into_view_if_needed()
                            await asyncio.sleep(0.2)
                            await button.click()
                            self.logger.debug(f"Clicked Generate Speech for slot {slot_num} via parent container")
                            await asyncio.sleep(0.3)
                            button_clicked = True
                except Exception as e:
                    self.logger.debug(f"Parent container approach failed for slot {slot_num}: {e}")

                if not button_clicked:
                    try:
                        self.logger.debug(f"Falling back to nth-index approach for slot {slot_num}")
                        # Match any "Generate" variant, then pick nth.
                        gen_selectors = ','.join(SELECTORS.get('generate_speech_btn', ['button:has-text("Generate Speech")']))
                        button_selector = f"({gen_selectors}) >> nth={slot_index}"
                        button = await self.page.wait_for_selector(button_selector, timeout=5000)

                        if button:
                            await button.scroll_into_view_if_needed()
                            await asyncio.sleep(0.2)
                            await button.click()
                            self.logger.debug(f"Clicked Generate Speech for slot {slot_num} via nth-index fallback")
                            await asyncio.sleep(0.3)
                            button_clicked = True
                        else:
                            self.logger.warning(f"Generate Speech button not found for slot {slot_num}")
                    except Exception as e:
                        self.logger.warning(f"Failed to click Generate Speech for slot {slot_num}: {e}")

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

            self.logger.debug(f"Found {title_count} title fields, {content_count} content fields")

            if title_count < expected_count or content_count < expected_count:
                error_msg = f"Template has insufficient fields: expected at least {expected_count}, found {title_count} titles and {content_count} contents"
                self.logger.error(error_msg)
                return False, error_msg

            if title_count > expected_count or content_count > expected_count:
                self.logger.debug(f"Template has {title_count} slots, using first {expected_count} for this version")

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
                    error_parts.append(f"Missing Section Title in slots: {empty_titles}")
                if empty_contents:
                    error_parts.append(f"Missing Section Content in slots: {empty_contents}")
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
        if self.no_save:
            self.logger.info("⏭️ SKIPPING SAVE (--no-save mode)")
            return True

        self.logger.debug("Waiting for form state to stabilize...")
        await asyncio.sleep(0.3)

        try:
            await self.page.evaluate('document.activeElement?.blur()')
        except Exception:
            pass

        validation_passed, error_msg = await self.validate_form_fields(expected_slots)
        if not validation_passed:
            self.logger.error(f"❌ Validation failed: {error_msg}")
            return False

        await asyncio.sleep(0.6)

        self.logger.info("💾 Saving...")

        # New AnyLive UI auto-saves (shows "Auto Saved") and may not have a Save button.
        # If we can find a Save button, click it; otherwise treat as success.
        if await self.safe_click("save_btn", "Save button"):
            await asyncio.sleep(2)
            return True

        # Wait for "Auto Saved" indicator (best-effort).
        try:
            await self.page.wait_for_selector('text="Auto Saved"', timeout=15000)
        except Exception:
            pass

        self.logger.warning("No Save button found; assuming auto-save UI.")
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
            successful_slots = 0
            failed_slots: list[int] = []
            for i in range(len(version.scripts)):
                audio_code = version.audio_codes[i] if i < len(version.audio_codes) else ""
                script = version.scripts[i]
                ok = await self.fill_and_generate_slot(i, audio_code, script, dry_run=self.dry_run)
                if ok:
                    successful_slots += 1
                else:
                    failed_slots.append(i + 1)

            version.failed_slots = failed_slots
            self.logger.info(f"Completed {successful_slots}/{len(version.scripts)} slots")
            if failed_slots:
                self.logger.warning(f"Failed slots: {failed_slots}")

            if successful_slots == 0:
                raise Exception("Failed to fill any slots")

            if not await self.save_version(len(version.scripts)):
                raise Exception("Failed to save version")

            # Go back to versions list using the in-app back button ("<") to avoid SPA state issues.
            try:
                await self.page.get_by_role("button", name="Back").click(timeout=3000)
            except Exception:
                try:
                    await self.page.locator('main button').first.click(timeout=3000)
                except Exception:
                    pass

            if self.no_save:
                self.logger.info(f"COMPLETED (not saved): {version.name}")
            else:
                if failed_slots:
                    self.logger.warning(f"PARTIAL SUCCESS: {version.name} (failed slots: {failed_slots})")
                else:
                    self.logger.info(f"SUCCESS: {version.name}")

            # Mark success only when all slots succeeded
            version.success = (len(failed_slots) == 0)
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


def print_version_info(version: Version, logger: logging.Logger):
    logger.info("")
    logger.info("=" * 70)
    logger.info(f"{version.name} - {len(version.scripts)} scripts")
    if version.products:
        logger.info(f"   Products: {', '.join(version.products[:3])}{'...' if len(version.products) > 3 else ''}")
    logger.info("=" * 70)


def generate_report(versions: List[Version], config: ClientConfig, timestamp: str, logger: logging.Logger, logs_dir: Optional[str] = None) -> Report:
    successful = sum(1 for v in versions if v.success)
    partial = sum(1 for v in versions if getattr(v, "failed_slots", None))
    failed = len(versions) - successful

    report = Report(
        timestamp=datetime.now().isoformat(),
        config={
            "grouping_strategy": "product_based",
            "max_scripts_per_version": config.max_scripts_per_version
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
                "error": v.error
            }
            for v in versions
        ]
    )

    logger.info("")
    logger.info("=" * 70)
    logger.info("📋 FINAL REPORT")
    logger.info("=" * 70)
    logger.info("")
    logger.info(f"Total: {report.total} | Success: {successful} ✅ | Partial: {partial} ⚠️ | Failed: {failed} ❌")
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
    no_save: bool = False,
    debug: bool = False,
    start_version: int = 1,
    limit: Optional[int] = None,
    app_support_dir: Optional[str] = None,
    log_callback: Optional[Callable[[str], None]] = None,
    debug_callback: Optional[Callable[[], None]] = None
) -> dict:
    """
    Main automation job function for GUI and programmatic execution.

    Args:
        config_path: Path to client config JSON file
        csv_path: Path to CSV file with scripts
        headless: Run browser in headless mode
        dry_run: Skip Generate Speech button clicks
        no_save: Skip Save button click
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

        if no_save:
            logger.info("⏭️ NO-SAVE MODE: Save button will be skipped")

        if debug:
            logger.info("🐛 DEBUG MODE: Browser will stay open after execution (non-blocking)")

        # Run automation
        automation = TTSAutomation(
            config=config,
            headless=headless,
            logger=logger,
            dry_run=dry_run,
            no_save=no_save,
            screenshots_dir=screenshots_dir
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
                logger.info("   (Automation will not auto-close the browser in debug mode)")
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
    parser.add_argument("--csv", type=str, help="Path to CSV file (auto-detects if not specified)")
    parser.add_argument("--start-version", type=int, default=1, help="Starting version number")
    parser.add_argument("--limit", type=int, help="Limit number of versions to process")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    parser.add_argument("--dry-run", action="store_true", help="Run without clicking Generate Speech")
    parser.add_argument("--no-save", action="store_true", help="Run without clicking Save button")
    parser.add_argument("--debug", action="store_true", help="Keep browser open after execution for debugging")

    parser.add_argument("--config", type=str, help="Path to client config JSON file")
    parser.add_argument("--client", type=str, help="Client name (loads configs/{NAME}.json)")
    parser.add_argument("--base-url", type=str, help="Override base URL")
    parser.add_argument("--voice", type=str, help="Override voice clone name")
    parser.add_argument("--template", type=str, help="Override version template name")
    parser.add_argument("--max-scripts", type=int, help="Override max scripts per version")

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

    config_path = None
    if args.client:
        config_path = f"configs/{args.client}.json"
    elif args.config:
        config_path = args.config
    else:
        config_path = "configs/default.json"

    cli_overrides = {}
    if args.base_url:
        cli_overrides['base_url'] = args.base_url
    if args.voice:
        cli_overrides['voice_name'] = args.voice
    if args.template:
        cli_overrides['version_template'] = args.template
    if args.max_scripts:
        cli_overrides['max_scripts_per_version'] = args.max_scripts

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
            with open(config_path, 'r', encoding='utf-8') as f:
                _cfg_raw = json.load(f)
                csv_from_config = _cfg_raw.get('csv')
        except Exception:
            csv_from_config = None

        csv_path = find_csv_file(args.csv or csv_from_config)
    except (FileNotFoundError, ValueError) as e:
        logger.error(f"❌ {e}")
        return

    df = load_csv(csv_path, logger)
    versions = parse_csv_data(df, config, logger)

    if not versions:
        logger.error("❌ No versions to process")
        return

    start_idx = args.start_version - 1
    if start_idx > 0:
        versions = versions[start_idx:]
        logger.info(f"Starting from version {args.start_version}")

    if args.limit:
        versions = versions[:args.limit]
        logger.info(f"Limited to {args.limit} versions")

    if args.dry_run:
        logger.info("🔇 DRY RUN MODE: Generate Speech will be skipped")

    if args.no_save:
        logger.info("⏭️ NO-SAVE MODE: Save button will be skipped")

    if args.debug:
        logger.info("🐛 DEBUG MODE: Browser will stay open after execution")

    automation = TTSAutomation(config=config, headless=args.headless, logger=logger, dry_run=args.dry_run, no_save=args.no_save)

    try:
        await automation.start_browser()

        for version in versions:
            print_version_info(version, logger)
            await automation.process_version(version)

    finally:
        if args.debug:
            logger.info("")
            logger.info("=" * 70)
            logger.info("🐛 DEBUG MODE: Leaving browser open for inspection (non-blocking)")
            logger.info("   Close the browser manually when you're done.")
            logger.info("=" * 70)
            return
        await automation.close()

    generate_report(versions, config, timestamp, logger)


if __name__ == "__main__":
    asyncio.run(main())
