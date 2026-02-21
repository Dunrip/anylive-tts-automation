# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- `pyproject.toml` with ruff and pytest configuration
- Unit test suite (`tests/`) covering CSV parsing, config loading, report generation, and session validation
- GitHub Actions CI pipeline (lint, format check, tests with coverage)
- `requirements-dev.txt` for development dependencies (pytest, ruff, coverage)
- `requirements-lock.txt` with pinned dependency versions
- `configs/default.example.json` as a tracked example config for new clones
- Pull request template (`.github/pull_request_template.md`)
- This changelog

### Changed
- `main()` refactored to delegate to `run_job()`, eliminating duplicated config/CSV/version logic
- `is_session_valid()` now reads and validates session JSON content (checks `setup_complete` flag and warns on stale sessions >30 days)
- Bare `except:` clauses replaced with `except Exception:` to preserve KeyboardInterrupt/SystemExit propagation
- Added explicit security comments for `--disable-web-security` browser flag

### Fixed
- Download button detection uses `data-dl-idx` attribute tagging with SVG path as fallback (more robust than pure SVG `d` matching)

## [2.0.0] - 2026-01-23

### Changed
- **Breaking**: Version naming changed from fixed 3-products-per-version to 1-product-per-version with auto-splitting at configurable max (default 10)
- External JSON configuration system replaces hardcoded constants
- Product-based grouping with overflow naming (`_v2`, `_v3`, etc.)

### Added
- Multi-client configuration support (`configs/` directory)
- macOS menu bar GUI application (`menubar_gui.py`)
- CLI overrides for all config values
- Download mode (`--download`, `--replace` flags)
- PyInstaller packaging support (`menubar_app.spec`)
