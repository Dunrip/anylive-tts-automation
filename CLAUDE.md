# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AnyLive TTS Automation is a Playwright-based web automation tool that creates TTS (Text-to-Speech) script versions on the AnyLive platform. It supports multi-client configuration, product-based version grouping, and both CLI and macOS menu bar GUI interfaces.

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
# Default run (uses configs/default.json)
python auto_tts.py

# With specific client config
python auto_tts.py --client mycompany

# Specify CSV file explicitly
python auto_tts.py --csv /path/to/file.csv
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
```

## Architecture

### Core Components

**auto_tts.py** - Main automation script (single-file design)
- `TTSAutomation` class: Handles browser automation and form filling
- `parse_csv_data()`: Reads CSV and groups scripts by product
- Session management with persistent browser state
- Resilient selector system with multiple fallback selectors
- Retry logic and validation for form fields

**menubar_gui.py** - macOS menu bar application
- Built with `rumps` for native macOS experience
- Wraps auto_tts.py functionality in GUI
- Stores data in ~/Library/Application Support/AnyLiveTTS/
- Designed for PyInstaller packaging (.app bundle)

**Configuration System**
- External JSON configs in `configs/` directory
- `configs/template.json` - Template for new clients
- `configs/default.json` - Default client configuration
- CLI overrides supported for all config values

### Data Flow

```
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

### Timeout Configuration

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
# Copy template
cp configs/template.json configs/new_client.json

# Edit config values (base_url, version_template, voice_name, etc.)

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

### Security
- **NEVER** commit `session_state.json` (contains auth cookies)
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
```
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
```
anylive-tts-automation/
├── auto_tts.py             # Main automation script
├── menubar_gui.py          # macOS menu bar app
├── requirements.txt        # Python dependencies
├── menubar_app.spec        # PyInstaller spec file
├── configs/                # Client configurations
│   ├── template.json       # Config template
│   └── default.json        # Default config
├── logs/                   # Generated at runtime (gitignored)
├── screenshots/            # Generated at runtime (gitignored)
├── browser_data/           # Generated at runtime (gitignored)
└── session_state.json      # Generated by --setup (gitignored)
```

### Important Files

- `auto_tts.py`: Main automation logic (lines 1-1100+)
- `menubar_gui.py`: Menu bar application wrapper
- `AGENTS.md`: Detailed architecture documentation (legacy, consider this CLAUDE.md authoritative)
- `README.md`: User-facing documentation
- `.gitignore`: Excludes logs, screenshots, session files, CSV files

## Recent Changes

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
