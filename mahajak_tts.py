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
from typing import List, Optional

import pandas as pd
from playwright.async_api import async_playwright, Page, BrowserContext

BASE_URL = "https://app.anylive.jp/scripts/207"
VERSION_PREFIX = "MAHAJAK_"
VERSION_TEMPLATE = "Version_Template"
VOICE_NAME = "Mahajak"
PRODUCTS_PER_VERSION = 3
SCRIPTS_PER_PRODUCT = 3
TOTAL_SLOTS_PER_VERSION = 9
DEFAULT_TIMEOUT = 30000
CLICK_TIMEOUT = 15000
NAVIGATION_TIMEOUT = 60000
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2
SESSION_FILE = "session_state.json"

ENABLE_VOICE_SELECTION = False
ENABLE_PRODUCT_INFO = False

SELECTORS = {
    "add_version_btn": [
        'button:has-text("Add New Version")',
        'text="+ Add New Version"',
        '[class*="add"] button',
    ],
    "version_name_input": [
        'input[placeholder*="Script Name"]',
        'input[placeholder*="Version Name"]',
        '[class*="modal"] input[type="text"]',
    ],
    "version_dropdown": [
        'text="Select Version"',
        '[role="combobox"]',
        'select',
    ],
    "template_option": [
        f'text="{VERSION_TEMPLATE}"',
        f'[role="option"]:has-text("{VERSION_TEMPLATE}")',
        f'option:has-text("{VERSION_TEMPLATE}")',
    ],
    "save_changes_btn": [
        'button:has-text("Save Changes")',
        '[class*="modal"] button:has-text("Save")',
        'button[type="submit"]',
    ],
    "voice_clone_dropdown": [
        'button[placeholder="Select Voice Clone"]',
        'button:has-text("Select Voice Clone")',
        '[role="combobox"]',
    ],
    "voice_option": [
        f'text="{VOICE_NAME}"',
        f'[role="option"]:has-text("{VOICE_NAME}")',
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
        'button:has-text("Generate Speech")',
        '[class*="generate"] button',
    ],
    "save_btn": [
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
class ScriptRow:
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
    success: bool = False
    error: Optional[str] = None


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


def setup_logging(timestamp: str) -> logging.Logger:
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    logger = logging.getLogger("mahajak_tts")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(EmojiFormatter())
    logger.addHandler(console_handler)
    
    file_handler = logging.FileHandler(logs_dir / f"mahajak_{timestamp}.log", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    logger.addHandler(file_handler)
    
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


def parse_csv_data(df: pd.DataFrame, logger: logging.Logger) -> List[Version]:
    df.columns = ["No", "Product Name", "Scene", "part", "TH Script", "col_f", "Audio Code", "col_h", "PIC"][:len(df.columns)]
    
    valid_rows = df[df["Product Name"].notna() & (df["Product Name"].str.strip() != "")]
    valid_rows = valid_rows[valid_rows["Product Name"] != "Product Name"]
    logger.info(f"Valid rows (with Product Name): {len(valid_rows)}")
    
    script_rows: List[ScriptRow] = []
    for idx, row in valid_rows.iterrows():
        script_rows.append(ScriptRow(
            product_name=str(row["Product Name"]).strip(),
            script_content=str(row["TH Script"]).strip() if pd.notna(row["TH Script"]) else "",
            audio_code=str(row["Audio Code"]).strip() if pd.notna(row["Audio Code"]) else "",
            row_number=int(idx) + 2
        ))
    
    products: List[List[ScriptRow]] = []
    current_product: List[ScriptRow] = []
    current_name = None
    
    for row in script_rows:
        if row.product_name != current_name:
            if current_product:
                products.append(current_product)
            current_product = [row]
            current_name = row.product_name
        else:
            current_product.append(row)
    if current_product:
        products.append(current_product)
    
    logger.info(f"Total products found: {len(products)}")
    
    versions: List[Version] = []
    version_num = 1
    
    for i in range(0, len(products), PRODUCTS_PER_VERSION):
        product_group = products[i:i + PRODUCTS_PER_VERSION]
        version_name = f"{VERSION_PREFIX}{version_num:02d}"
        
        product_names = []
        scripts = []
        audio_codes = []
        
        for product in product_group:
            product_names.append(product[0].product_name)
            for row in product[:SCRIPTS_PER_PRODUCT]:
                scripts.append(row.script_content)
                audio_codes.append(row.audio_code)
        
        versions.append(Version(
            name=version_name,
            products=product_names,
            scripts=scripts,
            audio_codes=audio_codes
        ))
        version_num += 1
    
    logger.info(f"Created {len(versions)} versions ({PRODUCTS_PER_VERSION} products each)")
    return versions


async def setup_login(logger: logging.Logger):
    logger.info("🔐 Starting login setup...")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        
        await page.goto("https://app.anylive.jp", wait_until="networkidle")
        logger.info("🌐 Navigated to AnyLive. Please log in manually.")
        
        input("Press Enter when you have completed login...")
        
        await context.storage_state(path=SESSION_FILE)
        logger.info(f"✅ Session saved to {SESSION_FILE}")
        
        await browser.close()
    
    logger.info("🎉 Setup complete! You can now run without --setup")


def is_session_valid() -> bool:
    return os.path.exists(SESSION_FILE)


class TTSAutomation:
    def __init__(self, headless: bool, logger: logging.Logger, dry_run: bool = False):
        self.headless = headless
        self.logger = logger
        self.dry_run = dry_run
        self.browser = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.playwright = None
    
    async def start_browser(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=self.headless)
        
        if is_session_valid():
            self.context = await self.browser.new_context(storage_state=SESSION_FILE)
            self.logger.debug("Loaded session from session_state.json")
        else:
            self.context = await self.browser.new_context()
            self.logger.warning("⚠️ No session found. Run with --setup first.")
        
        self.page = await self.context.new_page()
        self.page.set_default_timeout(DEFAULT_TIMEOUT)
    
    async def close(self):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
    
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
        screenshots_dir = Path("screenshots")
        screenshots_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = screenshots_dir / f"error_{version_name}_{timestamp}.png"
        await self.page.screenshot(path=str(path))
        self.logger.info(f"📸 Screenshot saved: {path}")
    
    async def clear_and_fill(self, element, value: str) -> bool:
        try:
            await element.scroll_into_view_if_needed()
            await element.click()
            await element.fill('')
            await element.fill(value)
            return True
        except Exception:
            return False
    
    async def select_template_from_dropdown(self) -> bool:
        try:
            await self.page.wait_for_selector('[role="option"]', timeout=CLICK_TIMEOUT)
            options = await self.page.query_selector_all('[role="option"]')
            for option in options:
                text = await option.inner_text()
                if text.strip() == VERSION_TEMPLATE:
                    await option.click()
                    self.logger.debug(f"Selected exact match: {VERSION_TEMPLATE}")
                    return True
            self.logger.error(f"Could not find exact match for {VERSION_TEMPLATE}")
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
                if text.strip() == VOICE_NAME:
                    await option.click()
                    self.logger.debug(f"Selected exact match: {VOICE_NAME}")
                    return True
            self.logger.error(f"Could not find exact match for {VOICE_NAME}")
            return False
        except Exception as e:
            self.logger.error(f"Failed to select voice: {e}")
            return False
    
    async def navigate_to_scripts(self):
        current_url = self.page.url
        if BASE_URL in current_url:
            self.logger.debug("Already on scripts page, skipping navigation")
            return
        self.logger.info(f"🌐 Navigating to {BASE_URL}")
        await self.page.goto(f"{BASE_URL}?page=1", wait_until="networkidle", timeout=NAVIGATION_TIMEOUT)
    
    async def create_new_version(self, name: str) -> bool:
        self.logger.info(f"📝 Creating version: {name}")
        
        if not await self.safe_click("add_version_btn", "Add New Version button"):
            return False
        
        await asyncio.sleep(0.5)
        
        if not await self.safe_fill("version_name_input", name, "Version Name input"):
            return False
        
        if not await self.safe_click("version_dropdown", "Version dropdown"):
            return False
        
        await asyncio.sleep(0.3)
        
        if not await self.select_template_from_dropdown():
            return False
        
        await asyncio.sleep(0.3)
        
        if not await self.safe_click("save_changes_btn", "Save Changes button"):
            return False
        
        await asyncio.sleep(1)
        self.logger.info(f"✅ Created: {name}")
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
        self.logger.info(f"🎙️ Selecting voice: {VOICE_NAME}")
        
        if not await self.safe_click("voice_clone_dropdown", "Voice Clone dropdown"):
            return False
        
        await asyncio.sleep(0.3)
        
        if not await self.select_voice_from_dropdown():
            return False
        
        await asyncio.sleep(0.3)
        return True
    
    async def fill_script_slots(self, scripts: List[str]) -> int:
        self.logger.info(f"📝 Filling {len(scripts)} script textareas...")
        
        filled = 0
        
        try:
            await self.page.wait_for_selector('textarea[aria-label="Section Content"]', timeout=CLICK_TIMEOUT)
            textareas = await self.page.query_selector_all('textarea[aria-label="Section Content"]')
            self.logger.debug(f"Found {len(textareas)} script textareas")
        except Exception as e:
            self.logger.error(f"Failed to find script textareas: {e}")
            return 0
        
        for i, script in enumerate(scripts):
            if i < len(textareas):
                try:
                    if await self.clear_and_fill(textareas[i], script):
                        filled += 1
                        await asyncio.sleep(0.1)
                except Exception as e:
                    self.logger.debug(f"Failed to fill slot {i+1}: {e}")
        
        self.logger.info(f"📊 Filled {filled}/{len(scripts)} slots")
        return filled
    
    async def fill_template_fields(self, audio_codes: List[str]) -> int:
        self.logger.info(f"🎵 Filling {len(audio_codes)} template fields with audio codes...")
        
        filled = 0
        
        try:
            await self.page.wait_for_selector('input[aria-label="Section Title"]', timeout=CLICK_TIMEOUT)
            template_inputs = await self.page.query_selector_all('input[aria-label="Section Title"]')
            self.logger.debug(f"Found {len(template_inputs)} template inputs")
        except Exception as e:
            self.logger.error(f"Failed to find template inputs: {e}")
            return 0
        
        for i, audio_code in enumerate(audio_codes):
            if i < len(template_inputs) and audio_code:
                try:
                    if await self.clear_and_fill(template_inputs[i], audio_code):
                        filled += 1
                        self.logger.debug(f"Filled template_{i+1} with: {audio_code}")
                        await asyncio.sleep(0.1)
                except Exception as e:
                    self.logger.debug(f"Failed to fill template {i+1}: {e}")
        
        self.logger.info(f"🎵 Filled {filled}/{len(audio_codes)} template fields")
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
        buttons = await self.page.query_selector_all('button:has-text("Generate Speech")')
        
        for i, button in enumerate(buttons[:count]):
            try:
                await button.click()
                triggered += 1
                await asyncio.sleep(0.2)
            except Exception as e:
                self.logger.debug(f"Failed to click Generate Speech {i+1}: {e}")
        
        self.logger.info(f"🔊 Triggered {triggered} generations")
        return triggered
    
    async def save_version(self) -> bool:
        self.logger.info("💾 Saving...")
        
        if not await self.safe_click("save_btn", "Save button"):
            return False
        
        await asyncio.sleep(2)
        await self.page.wait_for_url(f"{BASE_URL}*", timeout=NAVIGATION_TIMEOUT)
        return True
    
    async def process_version(self, version: Version) -> bool:
        try:
            await self.navigate_to_scripts()
            
            if not await self.create_new_version(version.name):
                raise Exception("Failed to create version")
            
            if ENABLE_VOICE_SELECTION:
                if not await self.select_voice_clone():
                    raise Exception("Failed to select voice")
            
            template_filled = await self.fill_template_fields(version.audio_codes)
            self.logger.debug(f"Template fields filled: {template_filled}")
            
            filled = await self.fill_script_slots(version.scripts)
            if filled == 0:
                raise Exception("Failed to fill any script slots")
            
            if ENABLE_PRODUCT_INFO:
                await self.fill_product_info()
            
            if self.dry_run:
                self.logger.info(f"🔇 DRY RUN: Skipping Generate Speech ({len(version.scripts)} buttons)")
            else:
                await self.trigger_generate_speech(len(version.scripts))
            
            if not await self.save_version():
                raise Exception("Failed to save version")
            
            self.logger.info(f"✅ SUCCESS: {version.name}")
            version.success = True
            return True
            
        except Exception as e:
            self.logger.error(f"Failed: {e}")
            await self.take_screenshot(version.name)
            version.error = str(e)
            self.logger.error(f"❌ FAILED: {version.name} - {e}")
            return False


def print_version_info(version: Version, logger: logging.Logger):
    logger.info("")
    logger.info("=" * 70)
    logger.info(f"🎯 {version.name}")
    for i, product in enumerate(version.products, 1):
        slots = f"slots {(i-1)*3+1}-{i*3}"
        logger.info(f"   Product {i}: {product} ({slots})")
    logger.info("=" * 70)


def generate_report(versions: List[Version], timestamp: str, logger: logging.Logger) -> Report:
    successful = sum(1 for v in versions if v.success)
    failed = len(versions) - successful
    
    report = Report(
        timestamp=datetime.now().isoformat(),
        config={
            "products_per_version": PRODUCTS_PER_VERSION,
            "scripts_per_product": SCRIPTS_PER_PRODUCT
        },
        total=len(versions),
        successful=successful,
        failed=failed,
        versions=[
            {
                "version": v.name,
                "products": v.products,
                "scripts": len(v.scripts),
                "success": v.success,
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
    logger.info(f"Total: {report.total} | Success: {successful} ✅ | Failed: {failed} ❌")
    logger.info("")
    logger.info("📑 VERSION → PRODUCTS MAPPING:")
    logger.info("-" * 70)
    
    for v in versions:
        status = "✅" if v.success else "❌"
        logger.info(f"{status} {v.name}:")
        for i, product in enumerate(v.products, 1):
            slots = f"slots {(i-1)*3+1}-{i*3}"
            logger.info(f"      Product {i}: {product} ({slots})")
        if v.error:
            logger.info(f"      ⚠️ Error: {v.error}")
        logger.info("")
    
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    report_path = logs_dir / f"report_{timestamp}.json"
    
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(asdict(report), f, ensure_ascii=False, indent=2)
    
    logger.info(f"📄 Report saved: {report_path}")
    return report


async def main():
    parser = argparse.ArgumentParser(description="MAHAJAK TTS Automation")
    parser.add_argument("--setup", action="store_true", help="One-time login setup")
    parser.add_argument("--csv", type=str, help="Path to CSV file (auto-detects if not specified)")
    parser.add_argument("--start-version", type=int, default=1, help="Starting version number")
    parser.add_argument("--limit", type=int, help="Limit number of versions to process")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    parser.add_argument("--dry-run", action="store_true", help="Run without clicking Generate Speech")
    
    args = parser.parse_args()
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    logger = setup_logging(timestamp)
    
    logger.info("🚀 MAHAJAK TTS AUTOMATION")
    logger.info("=" * 70)
    
    if args.setup:
        await setup_login(logger)
        return
    
    if not is_session_valid():
        logger.error("❌ No session found. Please run with --setup first.")
        logger.info("   python mahajak_tts.py --setup")
        return
    
    try:
        csv_path = find_csv_file(args.csv)
    except (FileNotFoundError, ValueError) as e:
        logger.error(f"❌ {e}")
        return
    
    df = load_csv(csv_path, logger)
    versions = parse_csv_data(df, logger)
    
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
    
    automation = TTSAutomation(headless=args.headless, logger=logger, dry_run=args.dry_run)
    
    try:
        await automation.start_browser()
        
        for version in versions:
            print_version_info(version, logger)
            await automation.process_version(version)
        
    finally:
        await automation.close()
    
    generate_report(versions, timestamp, logger)


if __name__ == "__main__":
    asyncio.run(main())
