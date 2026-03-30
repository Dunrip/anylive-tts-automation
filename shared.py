#!/usr/bin/env python3
"""Shared utilities for AnyLive automation scripts.

Extracted from auto_tts.py to enable reuse across auto_tts.py and auto_faq.py.
"""

import asyncio
import glob
import json
import logging
import os
import re
import shutil
import sys
import warnings
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Optional

import pandas as pd
from playwright.async_api import async_playwright, Page, BrowserContext


def get_playwright_cache_dir() -> Path:
    """Return the platform-specific Playwright browser cache directory.

    Returns:
        Path: The cache directory for Playwright browsers:
            - macOS: ~/Library/Caches/ms-playwright
            - Windows: %LOCALAPPDATA%/ms-playwright
            - Linux/Unix: ~/.cache/ms-playwright
    """
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "ms-playwright"
    elif sys.platform == "win32":
        localappdata = os.environ.get("LOCALAPPDATA", "")
        return Path(localappdata) / "ms-playwright"
    else:
        # Linux and other Unix-like systems
        return Path.home() / ".cache" / "ms-playwright"


# In packaged apps Playwright may default to looking for browsers inside the
# application bundle. Force use of the standard cache directory where
# `python -m playwright install chromium` downloads browsers.
os.environ.setdefault(
    "PLAYWRIGHT_BROWSERS_PATH",
    str(get_playwright_cache_dir()),
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
# Platform-aware keyboard modifier
MODIFIER_KEY = "Meta" if sys.platform == "darwin" else "Control"

DEFAULT_TIMEOUT = 30000
CLICK_TIMEOUT = 8000
NAVIGATION_TIMEOUT = 45000
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2
POST_AUTOSAVE_DELAY_SECONDS = 3.0
PRE_FILL_START_DELAY_SECONDS = 0.5
STATE_DIR = "state"
SESSION_FILE = "state/session_state.json"
DEBUG_SLOW_MO = 250  # ms between Playwright actions in debug mode


async def async_debug_pause(prompt: str = "Press Enter to continue...") -> None:
    """Async-safe ``input()`` that doesn't block the event loop."""
    await asyncio.to_thread(input, prompt)


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
# Console output formatting
# ---------------------------------------------------------------------------


class _Ansi:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    CYAN = "\033[36m"
    BOLD_WHITE = "\033[1;37m"


_ANSI_RE = re.compile(r"\033\[[0-9;]*m")
_color_enabled: bool = True


def _supports_color() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("TERM") == "dumb":
        return False
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def set_color_enabled(enabled: bool) -> None:
    global _color_enabled
    _color_enabled = enabled


def _c(text: str, *codes: str) -> str:
    """Wrap text in ANSI codes if color is enabled."""
    if not _color_enabled or not codes:
        return text
    return "".join(codes) + text + _Ansi.RESET


def strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def _visible_len(text: str) -> int:
    return len(strip_ansi(text))


def _pad(text: str, width: int) -> str:
    """Right-pad to *width* visible characters, accounting for ANSI."""
    return text + " " * max(0, width - _visible_len(text))


SYM = SimpleNamespace(
    OK="✓",
    FAIL="✗",
    RETRY="↻",
    SKIP="⊘",
    ARROW="→",
    DOT="·",
    WARN="⚠",
)

_SYM_COLORS: dict[str, str] = {
    "✓": _Ansi.GREEN,
    "✗": _Ansi.RED,
    "↻": _Ansi.YELLOW,
    "⊘": _Ansi.DIM,
    "⚠": _Ansi.YELLOW,
}


def fmt_banner(title: str, **context: str) -> str:
    """Format a startup banner with box drawing.

    >>> fmt_banner("ANYLIVE TTS", Client="myco", Mode="generate")
    ┌────────────────────────────────────────────────────────┐
    │  ANYLIVE TTS                                           │
    │  Client: myco · Mode: generate                         │
    └────────────────────────────────────────────────────────┘
    """
    ctx_parts = [f"{k}: {v}" for k, v in context.items() if v]
    ctx_str = (f" {SYM.DOT} ").join(ctx_parts) if ctx_parts else ""

    title_content = f"  {title}"
    ctx_content = f"  {ctx_str}" if ctx_str else ""

    min_width = 54
    inner = max(len(title_content), len(ctx_content), min_width) + 2

    bc = _Ansi.DIM
    lines: list[str] = [""]
    lines.append(_c("┌" + "─" * inner + "┐", bc))
    lines.append(
        _c("│", bc) + _pad(_c(title_content, _Ansi.BOLD_WHITE), inner) + _c("│", bc)
    )
    if ctx_content:
        lines.append(_c("│", bc) + _pad(ctx_content, inner) + _c("│", bc))
    lines.append(_c("└" + "─" * inner + "┘", bc))
    return "\n".join(lines)


def fmt_kv(pairs: list[tuple[str, str]], indent: int = 2) -> str:
    """Format aligned key-value pairs with colored keys.

    >>> fmt_kv([("Config", "tts.json"), ("CSV", "data.csv")])
      Config  tts.json
      CSV     data.csv
    """
    if not pairs:
        return ""
    max_key = max(len(k) for k, _ in pairs)
    lines: list[str] = []
    for key, value in pairs:
        colored_key = _c(key.ljust(max_key), _Ansi.CYAN)
        lines.append(" " * indent + colored_key + "  " + value)
    return "\n".join(lines)


def fmt_section(label: str, width: int = 56) -> str:
    """Format a section divider with label.

    >>> fmt_section("Processing 8 versions")
    ─── Processing 8 versions ─────────────────────────
    """
    prefix = "─── "
    suffix_len = max(1, width - len(prefix) - len(label) - 1)
    return (
        "\n"
        + _c(prefix, _Ansi.DIM)
        + _c(label, _Ansi.BOLD_WHITE)
        + _c(" " + "─" * suffix_len, _Ansi.DIM)
    )


def fmt_item(index: int, total: int, label: str) -> str:
    """Format an item header with progress counter.

    >>> fmt_item(1, 8, "01_ProductA (5 scripts)")
     [1/8] 01_ProductA (5 scripts)
    """
    counter = _c(f"[{index}/{total}]", _Ansi.DIM)
    return f"\n {counter} {_c(label, _Ansi.BOLD_WHITE)}"


def fmt_step(symbol: str, message: str, elapsed: str = "") -> str:
    """Format an indented step line with colored symbol.

    >>> fmt_step(SYM.OK, "Filled 5/5 fields", "3.2s")
           ✓ Filled 5/5 fields  3.2s
    """
    color = _SYM_COLORS.get(symbol, "")
    colored_sym = _c(symbol, color) if color else symbol
    line = f"       {colored_sym} {message}"
    if elapsed:
        line += "  " + _c(elapsed, _Ansi.DIM)
    return line


def fmt_result(ok: bool, detail: str) -> str:
    """Format a result line with arrow and status.

    >>> fmt_result(True, "3 scripts uploaded")
      → OK: 3 scripts uploaded
    """
    arrow = _c(SYM.ARROW, _Ansi.DIM)
    status = _c("OK", _Ansi.GREEN) if ok else _c("FAILED", _Ansi.RED)
    return f"  {arrow} {status}: {detail}"


def fmt_elapsed(seconds: float) -> str:
    """Format elapsed seconds for display.

    Returns ``'8.1s'`` for short durations, ``'2m 34s'`` for longer ones.
    """
    if seconds < 59.95:
        return f"{seconds:.1f}s"
    total_secs = int(round(seconds))
    minutes = total_secs // 60
    secs = total_secs % 60
    return f"{minutes}m {secs:02d}s"


def fmt_report_header(title: str, width: int = 56) -> str:
    """Format report opening: separator + title + separator."""
    sep = _c("─" * width, _Ansi.DIM)
    return f"\n{sep}\n  {_c(title, _Ansi.BOLD_WHITE)}\n{sep}"


def fmt_report_footer(width: int = 56) -> str:
    """Format report closing separator."""
    return _c("─" * width, _Ansi.DIM)


def fmt_summary(*parts: str) -> str:
    """Format a summary line with dot separators.

    >>> fmt_summary("Total: 8", "Success: 7 ✓", "Failed: 1 ✗")
      Total: 8 · Success: 7 ✓ · Failed: 1 ✗
    """
    dot = _c(f" {SYM.DOT} ", _Ansi.DIM)
    return "  " + dot.join(parts)


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


class ConsoleFormatter(logging.Formatter):
    """Console formatter: passes through messages, dims DEBUG level."""

    def format(self, record: logging.LogRecord) -> str:
        msg = record.getMessage()
        if record.levelno <= logging.DEBUG:
            return _c(msg, _Ansi.DIM)
        return msg


def EmojiFormatter(*args: Any, **kwargs: Any) -> ConsoleFormatter:
    """Deprecated: use :class:`ConsoleFormatter` instead."""
    warnings.warn(
        "EmojiFormatter is deprecated, use ConsoleFormatter",
        DeprecationWarning,
        stacklevel=2,
    )
    return ConsoleFormatter(*args, **kwargs)


class PlainFormatter(logging.Formatter):
    """Formatter that strips ANSI codes.  Used for file and callback handlers."""

    def __init__(
        self,
        template: str = "{time} | {level} | {message}",
        time_fmt: str = "%Y-%m-%d %H:%M:%S",
    ) -> None:
        super().__init__()
        self._template = template
        self._time_fmt = time_fmt

    def format(self, record: logging.LogRecord) -> str:
        msg = strip_ansi(record.getMessage())
        time_str = self.formatTime(record, self._time_fmt)
        return self._template.format(time=time_str, level=record.levelname, message=msg)


_LEVEL_MAP: dict[str, str] = {"WARNING": "WARN", "CRITICAL": "ERROR"}


class CallbackLogHandler(logging.Handler):
    def __init__(self, callback: Callable[[str, str], None]) -> None:
        super().__init__()
        self.callback = callback
        self.setFormatter(PlainFormatter())

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            level = _LEVEL_MAP.get(record.levelname, record.levelname)
            self.callback(msg, level)
        except Exception:
            self.handleError(record)


def setup_logging(
    timestamp: str,
    *,
    logger_name: str = "auto_tts",
    log_prefix: str = "auto_tts",
    logs_dir: Optional[str] = None,
    log_callback: Optional[Callable[[str, str], None]] = None,
    color: bool = True,
    verbosity: str = "normal",
) -> logging.Logger:
    """Configure logging with console, file, and optional callback handlers.

    Args:
        color: Enable ANSI colors on console.  Auto-disabled when stdout is
            not a TTY or the ``NO_COLOR`` env-var is set.
        verbosity: ``"quiet"`` (warnings only), ``"normal"`` (info), or
            ``"verbose"`` (debug on console).
    """
    set_color_enabled(color and _supports_color())

    console_level = {
        "quiet": logging.WARNING,
        "normal": logging.INFO,
        "verbose": logging.DEBUG,
    }.get(verbosity, logging.INFO)

    if logs_dir is None:
        logs_path = Path("logs")
    else:
        logs_path = Path(logs_dir)
    logs_path.mkdir(exist_ok=True)

    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    # Console — clean output, no timestamps (formatting functions provide structure)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_level)
    console_handler.setFormatter(ConsoleFormatter())
    logger.addHandler(console_handler)

    # File — detailed with timestamps, ANSI codes stripped
    file_handler = logging.FileHandler(
        logs_path / f"{log_prefix}_{timestamp}.log", encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        PlainFormatter(
            template="{time} | {level} | {message}",
            time_fmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger.addHandler(file_handler)

    # Callback — for app/GUI integration, ANSI codes stripped
    if log_callback:
        callback_handler = CallbackLogHandler(log_callback)
        callback_handler.setLevel(logging.DEBUG)
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
        debug: bool = False,
        screenshots_dir: Optional[str] = None,
        browser_data_subdir: str = "state/browser_data",
        session_filename: str = SESSION_FILE,
        login_url: str = "https://app.anylive.jp",
        base_url: str = "",
    ) -> None:
        self.headless = headless
        self.logger = logger
        self.dry_run = dry_run
        self.debug = debug
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
            slow_mo=250 if self.debug else 0,
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
                wait_until="domcontentloaded",
                timeout=NAVIGATION_TIMEOUT,
            )
            await asyncio.sleep(2)
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
                await el.press(f"{MODIFIER_KEY}+A")
                await el.press("Backspace")
                await self.page.keyboard.press(f"{MODIFIER_KEY}+V")
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
                    await element.press(f"{MODIFIER_KEY}+A")
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


async def _scrape_user_profile(page: "Page") -> dict[str, str]:
    logger = logging.getLogger(__name__)

    try:
        avatar_selectors = [
            'button[class*="avatar"]',
            'button[class*="profile"]',
            '[class*="avatar"] button',
            '[class*="profile"] button',
        ]

        avatar_button = None
        for selector in avatar_selectors:
            try:
                avatar_button = await page.wait_for_selector(
                    selector, timeout=3000, state="visible"
                )
                if avatar_button:
                    logger.debug(f"Found avatar button with selector: {selector}")
                    break
            except Exception:
                continue

        if not avatar_button:
            logger.warning("Could not find avatar button in header")
            return {}

        await avatar_button.click()
        await asyncio.sleep(0.5)

        try:
            dropdown = await page.wait_for_selector(
                '[class*="dropdown"], [class*="menu"], [role="menu"]',
                timeout=3000,
                state="visible",
            )
        except Exception:
            logger.warning("Avatar dropdown did not appear after clicking")
            return {}

        display_name = ""
        email = ""

        children = await dropdown.query_selector_all("*")
        for child in children:
            text = (await child.text_content() or "").strip()
            if not text or text in ("ADMIN", "Logout"):
                continue
            child_children = await child.query_selector_all("*")
            if len(child_children) > 0:
                continue
            if "@" in text and "." in text:
                email = text
            elif not display_name:
                display_name = text

        await page.keyboard.press("Escape")
        await asyncio.sleep(0.3)

        result = {}
        if display_name:
            result["display_name"] = display_name
        if email:
            result["email"] = email

        if result:
            logger.debug(f"Scraped user profile: {result}")
        else:
            logger.warning("Could not extract display_name or email from dropdown")

        return result

    except Exception as e:
        logger.warning(f"Error scraping user profile: {e}")
        return {}


# ---------------------------------------------------------------------------
# Login setup (shared)
# ---------------------------------------------------------------------------
async def setup_login(
    logger: logging.Logger,
    *,
    login_url: str = "https://app.anylive.jp",
    browser_data_subdir: str = "state/browser_data",
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
                        try:
                            with open(session_file, "r") as f:
                                session_data = json.load(f)
                            needs_update = False
                            if not session_data.get("setup_complete"):
                                session_data["setup_complete"] = True
                                session_data["timestamp"] = datetime.now().isoformat()
                                needs_update = True
                            if "email" not in session_data:
                                logger.info(
                                    "Email missing from session, scraping user profile..."
                                )
                                profile = await _scrape_user_profile(page)
                                if profile:
                                    session_data.update(profile)
                                    needs_update = True
                            if needs_update:
                                with open(session_file, "w") as f:
                                    json.dump(session_data, f)
                                logger.info(
                                    "Session updated with setup marker and profile"
                                )
                        except Exception as e:
                            logger.debug(f"Could not update session with profile: {e}")
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
            profile = await _scrape_user_profile(page)

            session_data = {
                "setup_complete": True,
                "timestamp": datetime.now().isoformat(),
            }
            session_data.update(profile)

            with open(session_file, "w") as f:
                json.dump(session_data, f)
            logger.info("Session saved to browser_data directory")
            logger.info(f"Setup marker saved to {session_file}")

        await context.close()

    logger.info("Setup complete! You can now run without --setup")


# ---------------------------------------------------------------------------
# Unified live-platform session management (auto_faq + auto_script)
# ---------------------------------------------------------------------------
LIVE_SESSION_FILE = "state/session_state_faq.json"
LIVE_BROWSER_DATA = "state/browser_data_faq"
LIVE_LOGIN_URL = "https://live.app.anylive.jp"


def get_live_session_paths(client: Optional[str]) -> tuple[str, str]:
    """Return (session_filename, browser_data_subdir) for the live platform.

    Both auto_faq.py and auto_script.py operate on the same site
    (live.app.anylive.jp) and share authentication.  This is the single
    source of truth for their session/browser-data paths.
    """
    if client:
        return (
            f"state/session_state_faq_{client}.json",
            f"state/browser_data_faq_{client}",
        )
    return LIVE_SESSION_FILE, LIVE_BROWSER_DATA


def get_last_client(tracking_file: str) -> Optional[str]:
    """Read the last-used client name from a JSON tracking file."""
    path = get_session_file_path(tracking_file)
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f).get("last_client")
        except Exception:
            return None
    return None


def save_last_client(tracking_file: str, client: str) -> None:
    """Persist the last-used client name to a JSON tracking file."""
    path = get_session_file_path(tracking_file)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"last_client": client}, f)


def ensure_client_config(
    client: str,
    config_type: str = "live",
    logger: Optional[logging.Logger] = None,
) -> str:
    """Ensure a client config directory and file exist, creating from default if needed.

    Returns the config file path (e.g. ``configs/<client>/live.json``).
    """
    config_dir = Path("configs") / client
    config_file = config_dir / f"{config_type}.json"
    default_file = Path("configs") / "default" / f"{config_type}.json"

    if config_file.exists():
        return str(config_file)

    if not default_file.exists():
        raise FileNotFoundError(
            f"Default config template not found: {default_file}\n"
            f"Cannot auto-create config for client '{client}'."
        )

    config_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(default_file, config_file)

    msg = (
        f"Created config for '{client}': {config_file}\n"
        f"   Update base_url in {config_file} before running automation."
    )
    if logger:
        logger.info(msg)

    return str(config_file)
