#!/usr/bin/env python3
"""Shared utilities for AnyLive automation scripts.

Extracted from auto_tts.py to enable reuse across auto_tts.py and auto_faq.py.
"""

import asyncio
import glob
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

import pandas as pd
from playwright.async_api import async_playwright, Page, BrowserContext

# In packaged apps Playwright may default to looking for browsers inside the
# application bundle. Force use of the standard macOS cache directory where
# `python -m playwright install chromium` downloads browsers.
os.environ.setdefault(
    "PLAYWRIGHT_BROWSERS_PATH",
    os.path.join(str(Path.home()), "Library", "Caches", "ms-playwright"),
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_TIMEOUT = 30000
CLICK_TIMEOUT = 8000
NAVIGATION_TIMEOUT = 45000
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2
POST_AUTOSAVE_DELAY_SECONDS = 3.0
PRE_FILL_START_DELAY_SECONDS = 0.5
STATE_DIR = "state"
SESSION_FILE = "state/session_state.json"


# ---------------------------------------------------------------------------
# JSONC loader (JSON with // comments)
# ---------------------------------------------------------------------------
def _strip_jsonc_comments(text: str) -> str:
    lines = []
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("//"):
            continue
        idx = line.find("//")
        while idx != -1:
            prefix = line[:idx]
            if prefix.count('"') % 2 == 0:
                line = prefix.rstrip()
                break
            idx = line.find("//", idx + 2)
        lines.append(line)
    return "\n".join(lines)


def load_jsonc(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()
    return json.loads(_strip_jsonc_comments(raw))


# ---------------------------------------------------------------------------
# App support directory management
# ---------------------------------------------------------------------------
_app_support_dir: Optional[str] = None


def set_app_support_dir(path: Optional[str]) -> None:
    global _app_support_dir
    _app_support_dir = path


def get_app_support_dir() -> Optional[str]:
    return _app_support_dir


def get_session_file_path(session_filename: str = SESSION_FILE) -> str:
    if _app_support_dir:
        path = os.path.join(_app_support_dir, session_filename)
    else:
        path = session_filename
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    return path


def get_browser_data_dir(subdir: str = "state/browser_data") -> str:
    """Return the directory used for Playwright persistent context.

    IMPORTANT: In a packaged macOS .app, the current working directory can be
    unexpected (often '/'), so using a relative path like './state/browser_data'
    can break silently (no profile/session persisted; permission errors).

    When running in menubar GUI mode we set _app_support_dir, so we store browser
    data under ~/Library/Application Support/AnyLiveTTS/<subdir>.
    """
    if _app_support_dir:
        return os.path.join(_app_support_dir, subdir)
    return f"./{subdir}"


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
class EmojiFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return f"{self.formatTime(record, '%H:%M:%S')} | {record.levelname} | {record.getMessage()}"


class CallbackLogHandler(logging.Handler):
    def __init__(self, callback: Callable[[str], None]) -> None:
        super().__init__()
        self.callback = callback
        self.setFormatter(EmojiFormatter())

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self.callback(msg)
        except Exception:
            self.handleError(record)


def setup_logging(
    timestamp: str,
    *,
    logger_name: str = "auto_tts",
    log_prefix: str = "auto_tts",
    logs_dir: Optional[str] = None,
    log_callback: Optional[Callable[[str], None]] = None,
) -> logging.Logger:
    if logs_dir is None:
        logs_path = Path("logs")
    else:
        logs_path = Path(logs_dir)
    logs_path.mkdir(exist_ok=True)

    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(EmojiFormatter())
    logger.addHandler(console_handler)

    file_handler = logging.FileHandler(
        logs_path / f"{log_prefix}_{timestamp}.log", encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    )
    logger.addHandler(file_handler)

    if log_callback:
        callback_handler = CallbackLogHandler(log_callback)
        callback_handler.setLevel(logging.INFO)
        logger.addHandler(callback_handler)

    return logger


# ---------------------------------------------------------------------------
# CSV utilities
# ---------------------------------------------------------------------------
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
        raise ValueError(
            f"Multiple CSV files found: {csv_files}. Use --csv to specify."
        )


def load_csv(path: str, logger: logging.Logger) -> pd.DataFrame:
    logger.info(f"Loading CSV: {path}")
    try:
        df = pd.read_csv(path, encoding="utf-8", header=0)
    except UnicodeDecodeError:
        logger.debug("UTF-8 failed, trying cp874 encoding")
        df = pd.read_csv(path, encoding="cp874", header=0)
    return df


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------
def is_session_valid(session_filename: str = SESSION_FILE) -> bool:
    session_file = get_session_file_path(session_filename)
    return os.path.exists(session_file)


# ---------------------------------------------------------------------------
# Base browser automation class
# ---------------------------------------------------------------------------
class BrowserAutomation:
    """Base class for Playwright-based browser automation.

    Subclasses provide their own SELECTORS dict and workflow logic.
    """

    SELECTORS: dict[str, list[str]] = {}

    def __init__(
        self,
        *,
        headless: bool = False,
        logger: logging.Logger,
        dry_run: bool = False,
        screenshots_dir: Optional[str] = None,
        browser_data_subdir: str = "browser_data",
        session_filename: str = SESSION_FILE,
        login_url: str = "https://app.anylive.jp",
        base_url: str = "",
    ) -> None:
        self.headless = headless
        self.logger = logger
        self.dry_run = dry_run
        self.screenshots_dir = screenshots_dir or "screenshots"
        self.browser_data_subdir = browser_data_subdir
        self.session_filename = session_filename
        self.login_url = login_url
        self.base_url = base_url
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.playwright = None

    async def start_browser(self) -> None:
        self.logger.info(
            f"PLAYWRIGHT_BROWSERS_PATH={os.environ.get('PLAYWRIGHT_BROWSERS_PATH')}"
        )
        self.playwright = await async_playwright().start()

        self.logger.info("Initializing browser with persistent context...")
        user_data_dir = get_browser_data_dir(self.browser_data_subdir)
        os.makedirs(user_data_dir, exist_ok=True)
        self.context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=self.headless,
            accept_downloads=True,
            args=[
                "--start-maximized",
                "--disable-web-security",
                "--disable-features=VizDisplayCompositor",
            ],
        )
        self.page = (
            self.context.pages[0]
            if self.context.pages
            else await self.context.new_page()
        )
        self.page.set_default_timeout(DEFAULT_TIMEOUT)

        if is_session_valid(self.session_filename):
            self.logger.info("Using saved session from browser_data directory")
            if not await self.validate_session():
                await self.close()
                raise Exception(
                    "Session expired or invalid. Please run setup again:\n"
                    "  python <script> --setup"
                )
            self.logger.info("Session is valid and authenticated")
        else:
            self.logger.error("No session found. Please run setup first:")
            self.logger.error("  python <script> --setup")
            raise Exception("No session file found")

    async def close(self) -> None:
        if self.context:
            await self.context.close()
        if self.playwright:
            await self.playwright.stop()

    async def validate_session(self) -> bool:
        try:
            self.logger.debug("Validating session...")
            await self.page.goto(
                self.base_url or self.login_url,
                wait_until="networkidle",
                timeout=30000,
            )
            current_url = self.page.url
            if "login" in current_url.lower():
                self.logger.error("Session expired - redirected to login page")
                return False
            self.logger.debug("Session validated successfully")
            return True
        except Exception as e:
            self.logger.error(f"Session validation failed: {e}")
            return False

    async def safe_click(
        self,
        selector_key: str,
        description: str,
        timeout: int = CLICK_TIMEOUT,
        force: bool = False,
    ) -> bool:
        selectors = self.SELECTORS.get(selector_key, [selector_key])
        for selector in selectors:
            try:
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
        selectors = self.SELECTORS.get(selector_key, [selector_key])
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

    async def take_screenshot(self, label: str) -> None:
        screenshots_dir = Path(self.screenshots_dir)
        screenshots_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = screenshots_dir / f"error_{label}_{timestamp}.png"
        await self.page.screenshot(path=str(path))
        self.logger.info(f"Screenshot saved: {path}")

    async def clear_and_fill(self, element, value: str, max_retries: int = 5) -> bool:
        """Robust fill helper for reactive UIs.

        AnyLive uses controlled inputs; .fill() may not commit.
        Strategy per attempt: fill/type -> verify -> JS -> verify -> clipboard paste -> verify.
        """

        async def _clipboard_paste(el, val: str) -> bool:
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

                # Clipboard paste fallback
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


# ---------------------------------------------------------------------------
# Login setup (shared)
# ---------------------------------------------------------------------------
async def setup_login(
    logger: logging.Logger,
    *,
    login_url: str = "https://app.anylive.jp",
    browser_data_subdir: str = "browser_data",
    session_filename: str = SESSION_FILE,
    gui_mode: bool = False,
) -> None:
    logger.info("Starting login setup...")
    session_file = get_session_file_path(session_filename)

    async with async_playwright() as p:
        logger.info("Initializing browser with persistent context...")
        logger.info(
            f"PLAYWRIGHT_BROWSERS_PATH={os.environ.get('PLAYWRIGHT_BROWSERS_PATH')}"
        )
        user_data_dir = get_browser_data_dir(browser_data_subdir)
        logger.info(f"Browser profile dir: {user_data_dir}")
        os.makedirs(user_data_dir, exist_ok=True)

        try:
            context = await p.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                headless=False,
                args=[
                    "--start-maximized",
                    "--disable-web-security",
                    "--disable-features=VizDisplayCompositor",
                ],
            )
        except Exception:
            logger.exception("Failed to launch Chromium persistent context")
            raise

        page = context.pages[0] if context.pages else await context.new_page()

        if not gui_mode:
            if is_session_valid(session_filename):
                logger.info(f"Found existing session file: {session_file}")
                logger.info("Verifying session validity...")
                try:
                    await page.goto(login_url, wait_until="networkidle", timeout=30000)
                    current_url = page.url
                    if "login" not in current_url.lower():
                        logger.info("Existing session is still valid!")
                        logger.info("Setup complete! You can now run without --setup")
                        await context.close()
                        return
                    else:
                        logger.warning("Session expired. Need to login again.")
                except Exception as e:
                    logger.warning(f"Session validation failed: {e}")
            else:
                logger.info("No existing session found.")
        else:
            logger.info("GUI mode: Always opening browser for manual login")

        logger.info("Opening browser for manual login...")
        await page.goto(login_url, wait_until="networkidle")
        logger.info(f"Navigated to {login_url}. Please log in manually.")

        if not gui_mode:
            input("Press Enter when you have completed login...")
        else:
            logger.info("GUI mode: Please complete login in the browser window...")
            try:
                await page.bring_to_front()
            except Exception:
                pass

            for i in range(60):
                await asyncio.sleep(1)
                try:
                    current_url = page.url
                    if "login" not in current_url.lower():
                        logger.info("Login detected automatically!")
                        break
                except Exception:
                    pass
                if i % 10 == 0:
                    logger.info(f"Waiting for login... ({60 - i}s remaining)")

            current_url = page.url
            if "login" in current_url.lower():
                logger.warning("Login timeout. You may need to try again.")

        current_url = page.url
        logger.info(f"Current URL: {current_url}")

        if "login" in current_url.lower():
            logger.warning("Still on login page. Please make sure you're logged in.")
        else:
            logger.info("Login detected!")

        if "login" in current_url.lower():
            logger.warning("Not saving session marker because login was not completed")
        else:
            with open(session_file, "w") as f:
                json.dump(
                    {
                        "setup_complete": True,
                        "timestamp": datetime.now().isoformat(),
                    },
                    f,
                )
            logger.info("Session saved to browser_data directory")
            logger.info(f"Setup marker saved to {session_file}")

        await context.close()

    logger.info("Setup complete! You can now run without --setup")
