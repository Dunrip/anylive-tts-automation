# Configuration Structure

This directory contains client-specific configurations for the AnyLive TTS automation suite.

## Directory Structure

```
configs/
├── CLAUDE.md           # This file
├── default/            # Default client (serves as template + fallback)
│   ├── tts.json        # TTS automation configuration
│   └── live.json       # FAQ/Script automation configuration
└── {client}/           # Custom client configurations
    ├── tts.json        # TTS automation configuration
    ├── live.json       # FAQ/Script automation configuration
    └── ...
```

## Configuration Files

### tts.json (TTS Automation)

Used by `auto_tts.py` for creating TTS script versions on `app.anylive.jp`.

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

**Fields:**
- `base_url` (required): AnyLive scripts page URL
- `version_template` (required): Template version name to clone from
- `voice_name` (required): Voice clone name for TTS generation
- `max_scripts_per_version` (default: 10): Maximum scripts per version (triggers auto-split)
- `enable_voice_selection` (default: false): Enable voice clone dropdown selection
- `enable_product_info` (default: false): Enable product name/selling point fields
- `csv_columns` (required): Maps CSV column names to expected fields

### live.json (FAQ/Script Automation)

Used by `auto_faq.py` and `auto_script.py` for Product Q&A and Set Live Content on `live.app.anylive.jp`.

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

**Fields:**
- `base_url` (required): Live interaction platform URL with session ID
- `audio_dir` (default: "downloads"): Directory containing audio files
- `audio_extensions` (default: [".mp3", ".wav"]): Supported audio file extensions
- `csv_columns` (required): Maps CSV column names to expected fields

## Creating a New Client Configuration

1. Copy the default folder:
   ```bash
   cp -r configs/default configs/new_client
   ```

2. Edit `configs/new_client/tts.json`:
   - Update `base_url` to your AnyLive scripts page
   - Update `version_template` to your template version name
   - Update `voice_name` to your voice clone name
   - Adjust `csv_columns` if your CSV has different column names

3. Edit `configs/new_client/live.json`:
   - Update `base_url` to your live interaction platform URL
   - Update `audio_dir` if audio files are in a different location
   - Adjust `csv_columns` if your CSV has different column names

4. Run with the new client:
   ```bash
   python auto_tts.py --client new_client
   python auto_faq.py --client new_client --csv faq.csv
   python auto_script.py --client new_client --csv scripts.csv
   ```

## Configuration Comments

Config files support inline `//` comments for documentation:

```json
{
  "base_url": "https://app.anylive.jp/scripts/XXX",  // Required: AnyLive scripts page
  "version_template": "Version_Template",             // Required: Template to clone
  "voice_name": "Voice Clone Name",                   // Required: Voice clone name
  "max_scripts_per_version": 10,                      // Default: 10
  "enable_voice_selection": false,                    // Default: false
  "enable_product_info": false,                       // Default: false
  "csv_columns": {
    "product_number": "No",
    "product_name": "Product Name",
    "script_content": "TH Script",
    "audio_code": "Audio Code"
  }
}
```

Comments are automatically stripped when loading via `load_jsonc()` in `shared.py`.

## Default Client

The `default/` folder serves dual purposes:
1. **Template**: Copy it to create new client configurations
2. **Fallback**: Used when no `--client` is specified

This eliminates the need for separate template files.

## CLI Overrides

All config values can be overridden via CLI arguments:

```bash
# Override voice name
python auto_tts.py --client mycompany --voice "Custom Voice"

# Override max scripts per version
python auto_tts.py --client mycompany --max-scripts 5

# Override base URL
python auto_tts.py --client mycompany --base-url "https://app.anylive.jp/scripts/YYY"

# Override version template
python auto_tts.py --client mycompany --template "Custom_Template"
```

## CSV Column Mapping

The `csv_columns` field allows flexible CSV structure mapping. Different clients can have different CSV column names:

```json
{
  "csv_columns": {
    "product_number": "No",           // Column name for product number
    "product_name": "Product Name",   // Column name for product name
    "script_content": "TH Script",    // Column name for script content
    "audio_code": "Audio Code"        // Column name for audio code
  }
}
```

This enables support for CSVs with different column naming conventions.

## Session Management

Each client maintains separate session files:
- TTS: `session_state.json` (shared across all TTS clients)
- FAQ: `session_state_faq_{client}.json` (per-brand)
- Script: Uses same session as FAQ (`session_state_faq_{client}.json`)

Run `--setup` once per client to establish authentication:

```bash
python auto_tts.py --setup
python auto_faq.py --setup --client mybrand
python auto_script.py --setup --client example
```
