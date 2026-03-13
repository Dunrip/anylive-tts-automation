# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AnyLive TTS Automation is a Playwright-based web automation tool that creates TTS (Text-to-Speech) script versions on the AnyLive platform (`app.anylive.jp`) and fills Product Q&A on the live interaction platform (`live.app.anylive.jp`). It supports multi-client configuration, product-based version grouping, and both CLI and macOS menu bar GUI interfaces.

## Development Setup

### Initial Setup

```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium

# One-time login setup (saves session)
python auto_tts.py --setup
```

### Running the Automation

```bash
# TTS automation (uses configs/default/tts.json)
python auto_tts.py

# With specific client config
python auto_tts.py --client mycompany

# Specify CSV file explicitly
python auto_tts.py --csv /path/to/file.csv

# FAQ automation (Product Q&A on live.app.anylive.jp)
python auto_faq.py --setup --client mybrand  # one-time login per brand
python auto_faq.py --setup --client brandB     # setup a second brand
python auto_faq.py --client mybrand --csv faq.csv  # run explicit brand (saves as last-used)
python auto_faq.py --csv faq.csv               # run last-used brand automatically
python auto_faq.py --dry-run                   # fill questions, skip audio upload
python auto_faq.py --debug                     # keep browser open
python auto_faq.py --start-product 5 --limit 3  # process subset
```

### Running Tests

```bash
pytest tests/ -v
```

### Testing and Debugging

```bash
# Dry run - fill forms without generating speech
python auto_tts.py --dry-run

# No-save mode - generate but don't save
python auto_tts.py --no-save

# Debug mode - keep browser open after execution
python auto_tts.py --debug

# Process subset of versions
python auto_tts.py --start-version 5 --limit 3

# Download specific versions by number
python auto_tts.py --download --versions 0,14-26
```

## Architecture

### Core Components

**shared.py** - Shared utilities

- `BrowserAutomation` base class: Browser lifecycle, `safe_click()`, `safe_fill()`, `clear_and_fill()`, `take_screenshot()`
- `setup_login()`: Parameterized login setup (login URL, browser data dir, session file)
- `load_jsonc()`: Load JSON with inline `//` comments support
- Logging: `EmojiFormatter`, `CallbackLogHandler`, `setup_logging()` (parameterized logger name/prefix)
- CSV: `find_csv_file()`, `load_csv()` (UTF-8 → CP874 fallback)
- Session: `is_session_valid()`, `get_session_file_path()`, `get_browser_data_dir()`
- Constants: `DEFAULT_TIMEOUT`, `CLICK_TIMEOUT`, `NAVIGATION_TIMEOUT`, etc.

**auto_tts.py** - TTS automation script

- `TTSAutomation` class: Handles TTS-specific browser automation and form filling
- `parse_csv_data()`: Reads CSV and groups scripts by product
- Imports shared utilities from `shared.py` (re-exports for backward compat with menubar_gui.py)
- TTS-specific `SELECTORS` dict
- Uses `browser_data/` and `session_state.json` for `app.anylive.jp`

**auto_faq.py** - Product FAQ automation script

- `FAQAutomation` class (extends `BrowserAutomation`): Fills Product Q&A on `live.app.anylive.jp`
- `parse_faq_csv()`: Reads CSV, groups by product number (int matching)
- `resolve_audio_file()`: Finds audio files in zero-padded subfolders or flat directory
- FAQ-specific `FAQ_SELECTORS` dict
- Multi-account support: `_get_faq_session_paths()`, `_get_last_faq_client()`, `_save_last_faq_client()`
- Per-client session: `session_state_faq_{client}.json` + `browser_data_faq_{client}/`
- Last-used client stored in `faq_last_client.json` (auto-selected when `--client` is omitted)

**menubar_gui.py** - macOS menu bar application

- Built with `rumps` for native macOS experience
- Wraps auto_tts.py functionality in GUI
- Stores data in ~/Library/Application Support/AnyLiveTTS/
- Designed for PyInstaller packaging (.app bundle)

#### Configuration System

- External JSON configs in nested `configs/{client}/` directories
- `configs/default/tts.json` - Default TTS client configuration
- `configs/default/live.json` - Default FAQ/Script client configuration
- `configs/{client}/tts.json` - TTS config for custom client
- `configs/{client}/live.json` - FAQ/Script config for custom client
- `default/` folder doubles as both template AND fallback config
- Config files support `//` inline comments (loaded via `load_jsonc()`)
- CLI overrides supported for all config values

### Data Flow

```text
CSV File → parse_csv_data() → List[Version] (grouped by product)
    ↓
For each version:
    1. Create version from template
    2. Fill form fields (audio codes, scripts)
    3. Trigger "Generate Speech" buttons
    4. Validate all fields
    5. Save version
    ↓
Generate JSON report in logs/
```

### CSV Structure

The script expects CSV files with these columns (column names configurable via config):

- **Column A (No)**: Product number → used in version name
- **Column B (Product Name)**: Product name → grouping key
- **Column E (TH Script)**: Script content → Section Content fields
- **Column G (Audio Code)**: Audio identifier → Section Title fields

### Version Grouping Logic

- **Product-based grouping**: Each product = 1+ versions
- **Auto-splitting**: Products with >10 scripts split into multiple versions
- **Naming pattern**: `{ProductNo}_{ProductName}` or `{ProductNo}_{ProductName}_v2` for overflow
- Product names are sanitized (spaces → underscores, special chars removed)

## Key Implementation Details

### Session Management

- Browser session persists via `session_state.json`
- One-time login with `--setup` flag
- Session validation before each run
- Session file excluded from git (contains auth cookies)

### Selector Strategy

The `SELECTORS` dict contains multiple fallback selectors for each UI element. This provides resilience against UI changes. Selectors are tried in order until one succeeds.

When AnyLive UI changes:

1. Locate the relevant key in `SELECTORS` dict (auto_tts.py:60-137)
2. Add new selector variations (most specific first)
3. Use browser DevTools to inspect elements

### Form Filling Best Practices

- **Always wait for form readiness**: `wait_for_form_ready()` polls for field count
- **Always validate before saving**: `validate_form_fields()` checks all fields
- **Use retry logic**: `clear_and_fill()` retries with value verification
- **Scroll elements into view** before interaction
- **Add delays after state changes** for UI stabilization

### Timeout Configuration (defined in `shared.py`)

```python
DEFAULT_TIMEOUT = 30000        # General waits
CLICK_TIMEOUT = 8000           # Element interactions
NAVIGATION_TIMEOUT = 45000     # Page navigations
MAX_RETRIES = 3                # Retry attempts
RETRY_DELAY_SECONDS = 2        # Between retries
```

### CSV Parsing Rules

- Encoding priority: UTF-8 → CP874 (Thai encoding fallback)
- Product name/number forward-fill: Empty cells inherit previous value
- Header row detection: Rows containing "Product Name" or "TH Version" are filtered
- Empty script validation: Rows must have either TH Script OR Audio Code

### Error Handling

- Screenshots on failure → `screenshots/error_{version}_{timestamp}.png`
- Continue processing next version even if current fails
- Final JSON report tracks success/failure per version
- Detailed logs in `logs/auto_tts_*.log` (DEBUG level)

## Configuration Reference

### Client Config Fields

```json
{
  "base_url": "https://app.anylive.jp/scripts/XXX",  // Required
  "version_template": "Version_Template",             // Required
  "voice_name": "Voice Clone Name",                   // Required
  "max_scripts_per_version": 10,                      // Default: 10
  "enable_voice_selection": false,                    // Default: false
  "enable_product_info": false,                       // Default: false
  "csv_columns": {                                    // Required
    "product_number": "No",
    "product_name": "Product Name",
    "script_content": "TH Script",
    "audio_code": "Audio Code"
  }
}
```

### CLI Override Examples

```bash
# Override config values
python auto_tts.py --voice "Custom Voice" --max-scripts 5
python auto_tts.py --base-url "https://app.anylive.jp/scripts/XXX"
python auto_tts.py --template "Template_Name"
```

## Common Development Tasks

### Adding a New Client Configuration

```bash
# Copy default folder as template
cp -r configs/default configs/new_client

# Edit config values in configs/new_client/tts.json and configs/new_client/live.json
# (base_url, version_template, voice_name, etc.)

# Run with new client
python auto_tts.py --client new_client
```

### Debugging Form Filling Issues

1. Use `--debug` to keep browser open
2. Check `logs/auto_tts_*.log` for DEBUG-level details
3. Screenshots saved automatically on errors
4. Use `--dry-run` to test without generating speech
5. Use `--no-save` to inspect filled forms manually

### Modifying Version Grouping Logic

Current logic groups by product name. To change:

1. Locate `parse_csv_data()` function in auto_tts.py
2. Modify the `product_groups` dictionary creation
3. Adjust version naming in the chunking logic

### Adding New Selectors

When UI elements change:

1. Run with `--debug` flag
2. Use browser DevTools to find new selectors
3. Add to `SELECTORS` dict (most specific selectors first)
4. Test with `--dry-run` to verify

## Important Constraints

### Git Commits

- **ALWAYS** set commit author to `Dunrip` (use `--author="Dunrip <>"` or equivalent)
- Never include the "Generated with Claude Code" footer or reaction prompts in any PR comments or code review output

### Security

- **NEVER** commit `session_state.json`, `session_state_faq.json`, or `session_state_faq_*.json` (contain auth cookies)
- **NEVER** commit CSV files (may contain sensitive product data)
- **NEVER** commit `logs/` directory (may contain sensitive data)
- All sensitive files are gitignored

### Session Requirements

- **MUST** run `--setup` before first use
- If session expires, re-run `--setup`
- Session validation happens on every run

### Version Naming

- Product names sanitized: special chars removed, spaces → underscores
- Pattern: `{ProductNo}_{ProductName}` or `{ProductNo}_{ProductName}_v2`
- Each product gets separate version(s)

### Form Filling

- Wait for form readiness before filling
- Validate all fields before saving
- Generate Speech triggers background processing (don't wait for completion)
- Voice selection and product info disabled by default

## Menu Bar App Specifics

### App Support Directory Structure

```text
~/Library/Application Support/AnyLiveTTS/
├── configs/              # User-editable configurations
├── logs/                 # Execution logs and reports
├── screenshots/          # Error screenshots
├── browser_data/         # Playwright persistent context
├── session_state.json    # Saved browser session
└── menubar_state.json    # GUI state
```

### PyInstaller Packaging Notes

- Single-file design supports easier packaging
- Playwright browsers installed at system level: `~/Library/Caches/ms-playwright`
- `PLAYWRIGHT_BROWSERS_PATH` env var set in both scripts
- Bundle configs as data files in .app/Contents/Resources/
- Session and logs remain external for persistence

### Menu Bar GUI Architecture

- `rumps` for native macOS menu bar integration
- Background threads for async operations (avoid blocking UI)
- UI updates queued via `_UI_QUEUE` for thread safety
- Logging to `~/Library/Application Support/AnyLiveTTS/logs/menubar.log`

## File Locations

### Repository Structure

```text
anylive-tts-automation/
├── shared.py               # Shared utilities (BrowserAutomation base, logging, CSV, session)
├── auto_tts.py             # TTS automation script
├── auto_faq.py             # Product FAQ automation script
├── auto_script.py          # Set Live Content script automation
├── menubar_gui.py          # macOS menu bar app
├── requirements.txt        # Python dependencies
├── menubar_app.spec        # PyInstaller spec file
├── configs/                # Client configurations (nested structure)
│   ├── CLAUDE.md           # Config structure documentation
│   ├── default/            # Default client (template + fallback)
│   │   ├── tts.json        # TTS configuration
│   │   └── live.json       # FAQ/Script configuration
│   └── {client}/           # Custom client configs
│       ├── tts.json        # TTS configuration
│       └── live.json       # FAQ/Script configuration
├── tests/                  # Unit tests
│   ├── test_shared.py      # Tests for shared utilities
│   └── test_auto_faq.py    # Tests for FAQ automation
├── logs/                   # Generated at runtime (gitignored)
├── screenshots/            # Generated at runtime (gitignored)
├── browser_data/           # TTS browser context (gitignored)
├── browser_data_faq/           # FAQ browser context, legacy (gitignored)
├── browser_data_faq_<client>/  # Per-brand FAQ browser context (gitignored)
├── session_state.json          # TTS session (gitignored)
├── session_state_faq.json      # FAQ session, legacy (gitignored)
├── session_state_faq_<client>.json  # Per-brand FAQ session (gitignored)
└── faq_last_client.json        # Last-used FAQ brand (gitignored)
```

### Important Files

- `shared.py`: Shared utilities — BrowserAutomation base class, logging, CSV, session
- `auto_tts.py`: TTS automation logic (imports from shared.py)
- `auto_faq.py`: FAQ automation logic (imports from shared.py)
- `menubar_gui.py`: Menu bar application wrapper
- `tests/`: Unit tests (77 tests covering CSV parsing, audio resolution, config, session)
- `AGENTS.md`: Detailed architecture documentation (legacy, consider this CLAUDE.md authoritative)
- `README.md`: User-facing documentation
- `.gitignore`: Excludes logs, screenshots, session files, CSV files

## FAQ Automation (`auto_faq.py`)

### Overview

Automates Product Q&A filling on `live.app.anylive.jp`. Reads CSV with product questions and audio codes, navigates to products, fills question fields, and uploads audio files.

### Separate Authentication

- FAQ uses `live.app.anylive.jp` (different site from TTS's `app.anylive.jp`)
- Each brand gets its own session: `session_state_faq_{client}.json` + `browser_data_faq_{client}/`
- Fallback to legacy `session_state_faq.json` / `browser_data_faq/` when no `--client` and no last-used
- Run `python auto_faq.py --setup --client <brand>` once per brand

### Multi-Account Behavior

| Usage | Session used |
|-------|-------------|
| `--client mybrand` | `session_state_faq_mybrand.json` + `browser_data_faq_mybrand/` |
| *(no `--client`)* | Last-used client (from `faq_last_client.json`) |
| *(no `--client`, first-ever run)* | Legacy `session_state_faq.json` / `browser_data_faq/` |

- `faq_last_client.json` is written whenever `--client` is passed on an automation run (not `--setup`)

### FAQ Config Fields

```json
{
  "base_url": "https://live.app.anylive.jp/live/SESSION_ID",
  "audio_dir": "downloads",
  "audio_extensions": [".mp3", ".wav"],
  "csv_columns": {
    "product_number": "No.",
    "product_name": "Product Name",
    "question": "Keywords",
    "audio_code": "Audio Code"
  }
}
```

### Audio File Resolution

Audio files are matched by `audio_code` in the configured `audio_dir`:

1. **Subfolder match**: `{zero_padded_number}_*/{audio_code}.mp3` (e.g., `01_Product_A/SFD1.mp3`)
2. **Flat fallback**: `{audio_dir}/{audio_code}.mp3`

### Key Differences from TTS

- No version splitting (1 product = 1 section on page)
- Product matching by integer comparison (CSV `No.` → int)
- Audio upload via `expect_file_chooser()` or hidden `input[type=file]`
- `--dry-run` fills questions but skips audio upload
- `--start-product` filters by product number (not index)

## Recent Changes

### Multi-Account FAQ Support

`auto_faq.py` now supports multiple brand accounts with isolated sessions. Each brand gets its own
`session_state_faq_{client}.json` and `browser_data_faq_{client}/`. The last-used client is saved
to `faq_last_client.json` and auto-selected when `--client` is omitted.

### FAQ Automation (auto_faq.py)

Added `auto_faq.py` for Product Q&A automation on `live.app.anylive.jp`. Extracted shared utilities into `shared.py` (`BrowserAutomation` base class, logging, CSV, session management). Added unit tests.

### Version 2.x Breaking Changes

**Version Naming Change** (from README):

- **Old logic (v1.x)**: Fixed 3 products per version, 3 scripts per product
- **New logic (v2.x)**: 1 product per version, variable scripts (max: 10)
- Impact: Version names differ from historical data
- Benefit: Flexible script counts, clearer product-to-version mapping

### UI Selector Updates

Recent commits updated selectors for new AnyLive UI version:

- "Add Version" button selector changes
- "Edit Script" tab click improvements
- Paragraph card-scoped name locators to avoid hidden fields
- Dialog-scoped selectors to prevent clicking wrong elements

When modifying selectors, always scope to nearest stable parent (modal, dialog, card) to avoid ambiguity.
