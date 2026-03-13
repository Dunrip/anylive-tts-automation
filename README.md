# AnyLive TTS Automation

Automate the creation of Text-to-Speech script versions on the AnyLive platform and fill Product Q&A on the live interaction platform. This suite provides a multi-client configuration system with intelligent product-based version grouping and batch audio management.

![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)
![Playwright](https://img.shields.io/badge/playwright-latest-green.svg)


## Table of Contents

- [Features](#features)
- [Quick Start](#quick-start)
- [Tools](#tools)
  - [auto_tts.py: TTS Script Creation](#auto_ttspy-tts-script-creation)
  - [auto_faq.py: Product FAQ](#auto_faqpy-product-faq)
  - [auto_script.py: Set Live Content](#auto_scriptpy-set-live-content)
  - [Menu Bar App (macOS)](#menu-bar-app-macos)
- [CLI Reference](#cli-reference)
- [Configuration](#configuration)
  - [Multi-Client Setup](#multi-client-setup)
  - [CSV Format](#csv-format)
- [Project Structure](#project-structure)
- [Troubleshooting](#troubleshooting)

## Features

**Automation and Efficiency**
- Multi-client support with external JSON configurations for different brands.
- Session persistence with one-time login setup.
- Automatic CSV detection in the project root.
- Headless browser mode for background execution.

**Content Management**
- Product-based grouping where one product equals one or more versions.
- Flat mode to pack scripts sequentially regardless of product boundaries.
- Batch download of generated audio files with selective version filtering.
- Automatic script upload and bulk deletion for live content.

**Reliability and Reporting**
- Retry logic with automatic screenshot capture on failures.
- Detailed logging to both console and timestamped files.
- Execution reports in JSON format for tracking success and failure.
- Dry run and debug modes for safe testing and inspection.

## Quick Start

1. **Install dependencies**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   playwright install chromium
   ```

2. **Setup authentication**
   ```bash
   python auto_tts.py --setup
   ```

3. **Run automation**
   ```bash
   # Place your CSV in the root directory
   python auto_tts.py
   ```

## Tools

### `auto_tts.py`: TTS Script Creation
Creates TTS script versions on `app.anylive.jp` by reading CSV data and filling web forms. It automatically groups scripts by product and triggers speech generation for each entry.

```bash
# Basic run with auto-detected CSV
python auto_tts.py

# Run for a specific client
python auto_tts.py --client mybrand

# Flat mode: pack 10 scripts per version regardless of product
python auto_tts.py --flat --max-scripts 10

# Download generated audio for specific versions
python auto_tts.py --download --versions 1-5,10
```

Versions are named `{No}_{ProductName}`. If a product exceeds the script limit, it splits into `{No}_{ProductName}_v2`, `_v3`, etc.

### `auto_faq.py`: Product FAQ
Fills Product Q&A on `live.app.anylive.jp` by uploading questions and corresponding audio files. It supports isolated sessions for multiple brands.

```bash
# Setup login for a specific brand
python auto_faq.py --setup --client mybrand

# Upload FAQ data from CSV
python auto_faq.py --client mybrand --csv faq.csv

# Dry run to verify form filling without uploading audio
python auto_faq.py --dry-run
```

**Audio File Structure**
Audio files are resolved from the `downloads` directory using the product number:
```
downloads/
  01_Product_A/SFD1.mp3, SFD2.mp3
  02_Product_B/SFD3.mp3, SFD4.mp3
```

### `auto_script.py`: Set Live Content
Uploads or deletes scripts on the "Set Live Content" tab of `live.app.anylive.jp`. This tool shares session data with `auto_faq.py` as they operate on the same site.

```bash
# Upload scripts from CSV
python auto_script.py --client example --csv scripts.csv

# Delete all scripts from all products
python auto_script.py --client example --delete-scripts

# Start processing from product number 3
python auto_script.py --client example --start-product 3
```

### Menu Bar App (macOS)
A native macOS menu bar application built with `rumps` that wraps the CLI functionality in a GUI. It stores user data in `~/Library/Application Support/AnyLiveTTS/`. Run it using `python menubar_gui.py`.

## CLI Reference

| Flag | Type | Tools | Description |
|------|------|-------|-------------|
| `--setup` | flag | all | One-time login setup |
| `--csv` | path | all | CSV file path (auto-detects) |
| `--client` | name | all | Client config name (loads configs/{NAME}/) |
| `--config` | path | all | Custom config JSON file path |
| `--start-version` | int | TTS | Start from version N |
| `--start-product` | int | FAQ, Script | Start from product N |
| `--limit` | int | all | Max items to process |
| `--headless` | flag | all | Headless browser mode |
| `--dry-run` | flag | all | Test without side effects |
| `--debug` | flag | all | Keep browser open after execution |
| `--download` | flag | TTS | Download audio files for all versions |
| `--versions` | string | TTS | Filter versions (e.g., `15-18,24,30`) |
| `--replace` | flag | TTS | Re-download existing files |
| `--verify` | flag | TTS | Verify downloads against CSV |
| `--flat` | flag | TTS | Ignore product boundaries, sequential packing |
| `--delete-scripts` | flag | Script | Delete all scripts from all products |
| `--base-url` | url | all | Override base URL |
| `--voice` | name | TTS | Override voice name |
| `--template` | name | TTS | Override template name |
| `--max-scripts` | int | TTS | Override max scripts per version |
| `--audio-dir` | path | FAQ, Script | Override audio directory |

## Configuration

### Multi-Client Setup
To create a new client, copy the `configs/default/` directory to `configs/{client_name}/` and modify the JSON files. Run the tool with `--client {client_name}` to load those settings.

**Example `tts.json`**
```json
{
  "base_url": "https://app.anylive.jp/scripts/XXX",
  "version_template": "Template_Name",
  "voice_name": "Voice_Clone_Name",
  "max_scripts_per_version": 10,
  "enable_voice_selection": false, // Enable voice dropdown
  "enable_product_info": false,    // Enable product name/selling point
  "csv_columns": {
    "product_number": "No.",
    "product_name": "Product Name",
    "script_content": "TH Script",
    "audio_code": "Audio Code"
  }
}
```
The `live.json` file uses a similar structure for FAQ and Script automation, focusing on `audio_dir` and `audio_extensions`.

### CSV Format
The tools use flexible column mapping. The default mapping expects:

| Column | Description |
|--------|-------------|
| No. | Product number used for grouping and file resolution |
| Product Name | Name used for versioning and grouping |
| TH Script | The actual text content for the script or question |
| Audio Code | Identifier used for the audio file name |

## Project Structure

```
anylive-tts-automation/
├── auto_tts.py             # TTS automation
├── auto_faq.py             # FAQ automation
├── auto_script.py          # Script automation
├── menubar_gui.py          # macOS menu bar app
├── shared.py               # Shared utilities
├── requirements.txt
├── configs/
│   ├── default/            # Default template and fallback
│   │   ├── tts.json
│   │   └── live.json
│   └── {client}/           # Custom client configs
├── state/                  # Runtime sessions and browser data
├── logs/                   # Execution logs and JSON reports
├── screenshots/            # Error captures
└── downloads/              # Downloaded audio files
```

## Troubleshooting

### Session Expired
If you encounter authentication errors, re-run the setup command: `python auto_tts.py --setup`.

### Multiple CSV Files
If the root directory contains multiple CSV files, specify the target file explicitly using the `--csv` flag.

### Config Not Found
Ensure the client name matches the folder name in the `configs/` directory. Use `ls configs/` to verify.

### Element Not Found
UI changes on AnyLive may break selectors. Run with `--debug` to inspect the browser state and check `screenshots/` for visual confirmation of the error.

### Audio Resolution Failure
Verify that your audio files are in the correct subdirectory within `downloads/` and that the file names match the `Audio Code` in your CSV.


