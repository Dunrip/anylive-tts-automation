# AGENTS.md

> **Note:** CLAUDE.md is the authoritative source for Claude Code. This file is maintained for compatibility with other AI coding assistants.

**Generated:** 2026-04-03 | **Commit:** 61d2dd8e | **Branch:** main

## OVERVIEW

Playwright-based web automation for TTS script creation, Product Q&A, and Set Live Content on AnyLive platform. Python CLI scripts + Tauri v2 desktop app (React + Rust + Python sidecar).

## STRUCTURE

```
anylive-tts-automation/
├── shared.py              # Base class + utilities (1095 lines)
├── auto_tts.py            # TTS automation — app.anylive.jp (3192 lines)
├── auto_faq.py            # FAQ automation — live.app.anylive.jp (1428 lines)
├── auto_script.py         # Script upload/delete (2381 lines)
├── configs/               # Multi-client JSON configs (JSONC with // comments)
│   ├── default/           # Template + fallback (tts.json, live.json)
│   └── {client}/          # Per-client overrides
├── tests/                 # pytest (8 files, CSV/config/audio tests — no browser mocks)
├── state/                 # Session files + Playwright contexts (GITIGNORED)
├── app/                   # Tauri v2 desktop app → see app/AGENTS.md
│   ├── src/               # React + TypeScript frontend (shadcn/ui)
│   ├── src-tauri/         # Rust backend (sidecar management)
│   └── sidecar/           # FastAPI bridge → see app/sidecar/AGENTS.md
└── .github/workflows/     # CI (4-job) + Release (multi-platform)
```

## WHERE TO LOOK

| Task | Location | Notes |
|-|-|-|
| TTS form filling | `auto_tts.py:606` TTSAutomation | Extends BrowserAutomation |
| FAQ product Q&A | `auto_faq.py:306` FAQAutomation | Per-brand sessions |
| Script upload/delete | `auto_script.py:159` ScriptAutomation | 3 modes: upload, delete, replace |
| Shared browser logic | `shared.py:523` BrowserAutomation | safe_click, safe_fill, clear_and_fill |
| CSV parsing | Each script's `parse_*_csv()` | Config-driven column mapping |
| Session management | `shared.py:882` setup_login() | Parameterized per-site |
| Config loading | `shared.py:95` load_jsonc() | JSON with // comments |
| Selector definitions | `auto_tts.py:60-137` SELECTORS | Multiple fallbacks per element |
| Desktop app | `app/` | See app/AGENTS.md |

## CONVENTIONS

- **Single-file design**: CLI scripts are self-contained for PyInstaller. NEVER add cross-file imports between auto_*.py files.
- **shared.py re-exports**: auto_tts.py re-exports shared utilities (`# noqa: F401`) for backward compat. NEVER remove.
- **JSONC configs**: Support `//` inline comments via `load_jsonc()`. Standard JSON parsers will fail.
- **Multi-account sessions**: FAQ/Script use per-client sessions (`session_state_faq_{client}.json`). TTS uses single shared session.
- **Forward-fill CSV**: Empty product name/number cells inherit previous row's values.
- **Encoding fallback**: UTF-8 → CP874 (Thai encoding).
- **run_job() contract**: Each CLI script exports `async def run_job(...)` for sidecar integration.

## ANTI-PATTERNS (THIS PROJECT)

- **NEVER** commit session files, CSV files, logs/, screenshots/ (auth cookies / sensitive data)
- **NEVER** use global selectors — ALWAYS scope to nearest stable parent (dialog, modal, card)
- **NEVER** use direct `page.fill()` — use `clear_and_fill()` with retry logic
- **NEVER** reduce timeouts without testing — masks real Playwright timing issues
- **NEVER** hardcode browser_data paths — use `get_browser_data_dir()` (macOS .app has CWD = `/`)
- **NEVER** skip `wait_for_form_ready()` before filling or `validate_form_fields()` before saving
- **NEVER** delete `configs/default/` — it's the fallback config for all scripts
- **EmojiFormatter** deprecated → use `ConsoleFormatter`
- **Git commits**: Author MUST be `Dunrip`. No AI attribution.

## COMMANDS

```bash
# Setup
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && playwright install chromium

# First-time login
python auto_tts.py --setup
python auto_faq.py --setup --client mybrand
python auto_script.py --setup --client example

# Run automation
python auto_tts.py --client mycompany --csv data.csv
python auto_faq.py --client mybrand --csv faq.csv
python auto_script.py --client example --csv scripts.csv

# Debug
python auto_tts.py --debug --dry-run   # Slow motion, no speech generation
python auto_tts.py --no-save           # Generate but don't save

# Tests
pytest tests/ -v
```

## NOTES

- Timeouts: DEFAULT=30s, CLICK=8s, NAVIGATION=45s, MAX_RETRIES=3, RETRY_DELAY=2s
- v2.x breaking: 1 product = 1+ versions (was 3 products/version in v1.x)
- `--headless --debug` silently disables debug (browser invisible)
- Playwright persistent context reuses browser state across runs
