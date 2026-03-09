# AnyLive TTS Automation

Automate the creation of TTS (Text-to-Speech) script versions on the AnyLive platform and fill Product Q&A on the live interaction platform. Supports multi-client configuration with product-based version grouping.

## Features

- ✅ **Multi-Client Support**: External JSON configuration for different brands/clients
- ✅ **Product-Based Grouping**: 1 product = 1 version (auto-splits if >10 scripts)
- ✅ **Flat Mode**: Override product grouping with `--flat` to pack scripts sequentially (N per version)
- ✅ **Session Management**: One-time login with `--setup`, session persists for future runs
- ✅ **Auto CSV Detection**: Automatically detects CSV files in project folder
- ✅ **Smart Version Naming**: `{ProductNo}_{ProductName}` or `{ProductNo}_{ProductName}_v2` for overflow
- ✅ **Error Handling**: Retry logic with screenshot capture on failures
- ✅ **Detailed Logging**: Console output with emoji indicators + file logs
- ✅ **JSON Reports**: Final execution report saved to `logs/`
- ✅ **Dry Run Mode**: Test without generating speech
- ✅ **Debug Mode**: Keep browser open for inspection
- ✅ **Menu Bar GUI**: Native macOS menu bar application (optional)
- ✅ **Product FAQ Automation**: Fill Product Q&A with questions + audio uploads on `live.app.anylive.jp`

## Installation

### 1. Install Dependencies

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install Python packages
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium
```

### 2. Prepare CSV File

Place your CSV file in the project root directory. The script will auto-detect it.

**CSV Structure**:
- **Column A** (No): Product number (e.g., "01", "02")
- **Column B** (Product Name): Product name (used for grouping and version naming)
- **Column E** (TH Script): Thai script content → Section Content fields
- **Column G** (Audio Code): Audio identifier → Section Title fields

**Version Grouping Logic**:
- Scripts are grouped by product name (column B)
- Each product gets its own version: `{ProductNo}_{ProductName}`
- If a product has >10 scripts, it splits into multiple versions:
  - First 10 scripts: `01_Product_Name`
  - Next 10 scripts: `01_Product_Name_v2`
  - Next 10 scripts: `01_Product_Name_v3`, etc.

### ⚠️ Breaking Change from Previous Versions

**Version Naming Change**:
- **Old logic (v1.x)**: Fixed 3 products per version, 3 scripts per product
  - Example: `CLIENT_01` contains Products 1-3 (9 scripts total)
- **New logic (v2.x)**: 1 product per version, variable scripts (default max: 10)
  - Example: `01_JBL_Speaker` contains Product 1 only (8 scripts)

**Impact**: Version names will differ from historical data. This change enables:
- Flexible script counts per product (not fixed to 3)
- Auto-splitting for products with >10 scripts
- Clearer product-to-version mapping

**Migration**: No code changes needed. New versions will use new naming. Existing versions in AnyLive remain unchanged.

## Multi-Client Setup

### Quick Start (Using Default Config)

```bash
# Uses configs/default.json by default
python auto_tts.py --setup
python auto_tts.py
```

### Creating a New Client Configuration

1. **Copy the template**:
   ```bash
   cp configs/template.json configs/new_client.json
   ```

2. **Edit the config**:
   ```json
   {
     "base_url": "https://app.anylive.jp/scripts/XXX",
     "version_template": "Version_Template",
     "voice_name": "Voice Clone Name",
     "max_scripts_per_version": 10,
     "enable_voice_selection": false,
     "enable_product_info": false,
     "csv_columns": {
       "product_number": "No",
       "product_name": "Product Name",
       "script_content": "TH Script",
       "audio_code": "Audio Code"
     }
   }
   ```

3. **Run with your client**:
   ```bash
   python auto_tts.py --client new_client
   ```

### Available Configurations

- `configs/default.json` - Default TTS client configuration
- `configs/template.json` - Template for creating new TTS client configs
- `configs/faq_template.json` - Template for FAQ automation configs

## Usage

### First Time: Setup Authentication

```bash
python auto_tts.py --setup
```

This will:
1. Open a browser
2. Navigate to AnyLive
3. Wait for you to login manually
4. Save session to `session_state.json`

### Normal Run

```bash
# Default (uses configs/default.json)
python auto_tts.py

# Specify client config
python auto_tts.py --client mycompany

# Custom config file
python auto_tts.py --config /path/to/config.json

# Override config values via CLI
python auto_tts.py --client mycompany --voice "Custom Voice" --max-scripts 5

# Or specify CSV explicitly
python auto_tts.py --csv /path/to/other.csv

# Start from version 5, process only 3 versions
python auto_tts.py --start-version 5 --limit 3

# Run in headless mode (no browser window)
python auto_tts.py --headless

# Dry run mode (fill forms but skip Generate Speech)
python auto_tts.py --dry-run

# No-save mode (fill and generate but skip Save button)
python auto_tts.py --no-save

# Debug mode (keep browser open after execution)
python auto_tts.py --debug

# Flat mode: ignore product grouping, pack N scripts per version sequentially
python auto_tts.py --flat --max-scripts 10

# Flat mode + dry run (preview versions without browser interaction)
python auto_tts.py --flat --max-scripts 10 --dry-run --no-save
```

## CLI Options

### Basic Options

| Option | Type | Description |
|--------|------|-------------|
| `--setup` | flag | One-time login setup, saves session to `session_state.json` |
| `--csv` | path | Path to CSV file (auto-detects if not specified) |
| `--start-version` | int | Starting version number (default: 1) |
| `--limit` | int | Max versions to process |
| `--headless` | flag | Run browser in headless mode |
| `--dry-run` | flag | Fill forms but skip Generate Speech buttons |
| `--no-save` | flag | Fill and generate but skip Save button |
| `--debug` | flag | Keep browser open after execution for debugging |
| `--flat` | flag | Ignore product grouping; pack all scripts sequentially into fixed-size batches (use with `--max-scripts`) |

### Configuration Options

| Option | Type | Description |
|--------|------|-------------|
| `--client` | name | Load config from `configs/{NAME}.json` |
| `--config` | path | Path to custom config JSON file |
| `--base-url` | url | Override base URL from config |
| `--voice` | name | Override voice clone name from config |
| `--template` | name | Override version template name from config |
| `--max-scripts` | int | Override max scripts per version from config |

## Project Structure

```
anylive-tts-automation/
├── shared.py               # Shared utilities (browser base class, logging, CSV, session)
├── auto_tts.py             # TTS automation script (CLI)
├── auto_faq.py             # Product FAQ automation script (CLI)
├── menubar_gui.py          # macOS menu bar application
├── menubar_app.spec        # PyInstaller specification
├── requirements.txt        # Dependencies
├── .gitignore              # Ignore logs, screenshots, session, csv
├── configs/                # Client configurations
│   ├── template.json       # TTS config template
│   ├── faq_template.json   # FAQ config template
│   └── default.json        # Default TTS config
├── tests/                  # Unit tests
│   ├── test_shared.py      # Tests for shared utilities
│   └── test_auto_faq.py    # Tests for FAQ automation
├── session_state.json      # TTS login session (gitignored)
├── session_state_faq.json  # FAQ login session (gitignored)
├── *.csv                   # Input CSV files
├── browser_data/           # TTS browser context (gitignored)
├── browser_data_faq/       # FAQ browser context (gitignored)
├── logs/                   # Created at runtime (gitignored)
│   ├── auto_tts_*.log
│   ├── auto_faq_*.log
│   ├── menubar.log
│   └── report_*.json
└── screenshots/            # Created at runtime (gitignored)
    └── error_*.png
```

## Output

### Console Output (Example)

```
12:34:56 | INFO | 🚀 ANYLIVE TTS AUTOMATION
12:34:56 | INFO | ======================================================================
12:34:57 | INFO | 📋 Loaded config: configs/default.json
12:34:57 | INFO | 📂 Loading CSV: scripts.csv
12:34:57 | INFO | Valid rows: 45
12:34:57 | INFO | Total script rows: 45
12:34:57 | INFO | Found 3 unique products
12:34:57 | INFO | Created 4 versions total
12:35:00 | INFO | ======================================================================
12:35:00 | INFO | 01_JBL_Endurance_Zone - 8 scripts
12:35:00 | INFO |    Products: JBL Endurance Zone
12:35:00 | INFO | ======================================================================
12:35:01 | INFO | ✅ SUCCESS: 01_JBL_Endurance_Zone
12:35:02 | INFO | ======================================================================
12:35:02 | INFO | 02_Samsung_Galaxy - 10 scripts
12:35:02 | INFO |    Products: Samsung Galaxy
12:35:02 | INFO | ======================================================================
12:35:03 | INFO | ✅ SUCCESS: 02_Samsung_Galaxy
12:35:04 | INFO | ======================================================================
12:35:04 | INFO | 02_Samsung_Galaxy_v2 - 12 scripts
12:35:04 | INFO |    Products: Samsung Galaxy
12:35:04 | INFO | ======================================================================
12:35:05 | INFO | ✅ SUCCESS: 02_Samsung_Galaxy_v2
```

### JSON Report (`logs/report_*.json`)

```json
{
  "timestamp": "2026-01-23T12:34:56.789Z",
  "config": {
    "grouping_strategy": "product_based",
    "max_scripts_per_version": 10
  },
  "total": 4,
  "successful": 4,
  "failed": 0,
  "versions": [
    {
      "version": "01_JBL_Endurance_Zone",
      "product_number": "01",
      "products": ["JBL Endurance Zone"],
      "scripts": 8,
      "success": true,
      "error": null
    },
    {
      "version": "02_Samsung_Galaxy",
      "product_number": "02",
      "products": ["Samsung Galaxy"],
      "scripts": 10,
      "success": true,
      "error": null
    },
    {
      "version": "02_Samsung_Galaxy_v2",
      "product_number": "02",
      "products": ["Samsung Galaxy"],
      "scripts": 12,
      "success": true,
      "error": null
    }
  ]
}
```

## Version Grouping Examples

### Example 1: Single Product, <10 Scripts

**CSV Input:**
```
No  | Product Name         | TH Script | Audio Code
01  | JBL Endurance Zone   | Script 1  | Audio 1
01  | JBL Endurance Zone   | Script 2  | Audio 2
... (total 8 scripts)
```

**Result:**
- 1 version created: `01_JBL_Endurance_Zone` (8 scripts)

### Example 2: Single Product, >10 Scripts (Overflow)

**CSV Input:**
```
No  | Product Name    | TH Script  | Audio Code
02  | Samsung Galaxy  | Script 1   | Audio 1
02  | Samsung Galaxy  | Script 2   | Audio 2
... (total 23 scripts)
```

**Result:**
- 3 versions created:
  - `02_Samsung_Galaxy` (scripts 1-10)
  - `02_Samsung_Galaxy_v2` (scripts 11-20)
  - `02_Samsung_Galaxy_v3` (scripts 21-23)

### Example 3: Multiple Products

**CSV Input:**
```
No  | Product Name    | Scripts Count
01  | JBL Speaker     | 8
02  | Samsung TV      | 15
03  | LG Monitor      | 3
```

**Result:**
- 4 versions created:
  - `01_JBL_Speaker` (8 scripts)
  - `02_Samsung_TV` (10 scripts)
  - `02_Samsung_TV_v2` (5 scripts)
  - `03_LG_Monitor` (3 scripts)

### Example 4: Flat Mode (Ignore Product Boundaries)

Used when you want a fixed number of scripts per version regardless of which product they belong to.

**Command:**
```bash
python auto_tts.py --flat --max-scripts 10
```

**CSV Input** (34 rows across many products):
```
No  | Product Name  | TH Script | Audio Code
0.1 | ค่าขนส่ง       | Script 1  | GG1
0.2 | AI หรือคน     | Script 2  | GG2
... (34 rows total across 34 products)
```

**Result** (4 versions, ignoring product boundaries):
- `batch_01` — scripts 1–10 (mixed products)
- `batch_02` — scripts 11–20 (mixed products)
- `batch_03` — scripts 21–30 (mixed products)
- `batch_04` — scripts 31–34 (mixed products)

## Configuration Reference

### Client Config Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `base_url` | string | required | AnyLive scripts page URL |
| `version_template` | string | required | Template version to clone from |
| `voice_name` | string | required | Voice clone name for TTS |
| `max_scripts_per_version` | int | 10 | Maximum scripts per version (triggers split) |
| `enable_voice_selection` | bool | false | Enable voice clone dropdown selection |
| `enable_product_info` | bool | false | Enable product name/selling point fields |
| `csv_columns` | object | required | CSV column mapping (see below) |

### CSV Column Mapping

```json
{
  "product_number": "No",
  "product_name": "Product Name",
  "script_content": "TH Script",
  "audio_code": "Audio Code"
}
```

Allows different clients to have different CSV structures.

## Troubleshooting

### Session Expired

If you get authentication errors:

```bash
python auto_tts.py --setup
```

### Multiple CSV Files Found

If you have multiple CSV files in the project folder:

```bash
python auto_tts.py --csv scripts.csv
```

### Config File Not Found

Make sure you're using the correct client name:

```bash
# Check available configs
ls configs/

# Use correct client name
python auto_tts.py --client mycompany
```

### Check Logs

Detailed logs are saved to `logs/auto_tts_TIMESTAMP.log`

### Screenshots on Error

When errors occur, screenshots are automatically saved to `screenshots/error_VERSION_TIMESTAMP.png`

## Migration from Hardcoded Configuration

If you have an older version with hardcoded constants, the new version is backward compatible:

1. **Default behavior**: Runs with `configs/default.json` which has the same values as old hardcoded constants
2. **To customize**: Create a new config file or use CLI overrides
3. **Old constants removed**:
   - `BASE_URL` → `config.base_url`
   - `VERSION_PREFIX` → Replaced by product number from CSV column A
   - `VERSION_TEMPLATE` → `config.version_template`
   - `VOICE_NAME` → `config.voice_name`
   - `ENABLE_VOICE_SELECTION` → `config.enable_voice_selection`
   - `ENABLE_PRODUCT_INFO` → `config.enable_product_info`
   - `PRODUCTS_PER_VERSION` / `SCRIPTS_PER_PRODUCT` → Removed; replaced by product-based grouping with `max_scripts_per_version`

## Menu Bar Application (macOS)

A native macOS menu bar application is available for team-friendly usage:

### Features
- Native macOS menu bar integration
- All CLI functionality accessible via GUI
- Stores data in `~/Library/Application Support/AnyLiveTTS/`
- Built with `rumps` for native experience
- PyInstaller-ready for .app bundle distribution

### Running Menu Bar App
```bash
# Run the menu bar app
python menubar_gui.py
```

### Menu Bar App Data Location
```
~/Library/Application Support/AnyLiveTTS/
├── configs/              # User-editable configurations
├── logs/                 # Execution logs (menubar.log, auto_tts_*.log)
├── screenshots/          # Error screenshots
├── browser_data/         # Browser persistent context
├── session_state.json    # Saved browser session
└── menubar_state.json    # GUI state
```

## App Compilation

The project supports PyInstaller compilation for macOS .app bundles:

```bash
# Build menu bar app (requires menubar_app.spec)
pyinstaller menubar_app.spec

# Resulting .app bundle
dist/AnyLiveTTS.app
```

**App structure:**
```
AnyLiveTTS.app/
├── Contents/
│   ├── MacOS/
│   │   └── AnyLiveTTS (executable)
│   └── Resources/
│       └── configs/
│           ├── template.json
│           └── default.json
```

User data remains in `~/Library/Application Support/AnyLiveTTS/` for persistence.

## Notes

- Each product is grouped by product name (column B) regardless of how many rows it spans
- Same product number (column A) across different products is allowed
- Product names are sanitized for version naming (spaces → underscores, special chars removed)
- Clicking "Generate Speech" triggers background AI processing - the script doesn't wait for completion
- Voice selection and product info filling are disabled by default (can be enabled in config)
- Session file (`session_state.json`) is excluded from git via `.gitignore`
- Browser data (`browser_data/`) is excluded from git via `.gitignore`
- Use `--dry-run` to test form filling without generating speech
- Use `--no-save` to test without saving (useful for debugging)
- Use `--debug` to inspect the browser state after execution

## Product FAQ Automation

A separate script (`auto_faq.py`) automates filling Product Q&A on `live.app.anylive.jp`. After generating and downloading audio files with the TTS workflow, use this to upload questions and audio to each product.

### FAQ Setup

```bash
# One-time login (separate site, separate session)
python auto_faq.py --setup

# Run with CSV
python auto_faq.py --csv FAQ.csv

# Use a client config
python auto_faq.py --client mybrand_faq

# Dry run (fill questions, skip audio upload)
python auto_faq.py --dry-run

# Debug mode
python auto_faq.py --debug

# Process subset of products
python auto_faq.py --start-product 5 --limit 3

# Override audio directory
python auto_faq.py --audio-dir ./my_audio
```

### FAQ Configuration

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

### Audio File Structure

Audio files are resolved from `audio_dir` using the product number:
```
downloads/
  01_Product_A/SFD1.mp3, SFD2.mp3
  02_Product_B/SFD3.mp3, SFD4.mp3
```

## Recent Updates

### Product FAQ Automation
Added `auto_faq.py` for automating Product Q&A filling on `live.app.anylive.jp`. Extracted shared
utilities into `shared.py` for code reuse between TTS and FAQ scripts. Added unit tests.

### Flat Mode (`--flat`)
Added `--flat` CLI flag to override the default product-based grouping. In flat mode, all
scripts are packed sequentially into fixed-size batches (set with `--max-scripts`). Versions
are named `batch_01`, `batch_02`, etc. instead of by product name. Useful when you want
a fixed number of slots per version regardless of product boundaries.

### UI Selector Improvements
Recent commits updated selectors for new AnyLive UI version:
- Improved "Add Version" button detection
- Optimized "Edit Script" tab click speed
- Scoped selectors to paragraph cards to avoid hidden fields
- Dialog-scoped selectors to prevent clicking wrong elements

### Menu Bar Application
Added native macOS menu bar application for improved team usability and easier distribution.

## Support

For issues or questions, please check the logs for detailed error messages or review the configuration documentation above.
