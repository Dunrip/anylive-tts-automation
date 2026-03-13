"""Tests for auto_script.py — CSV parsing, audio resolution, config loading."""

import logging
from pathlib import Path

import pytest

from auto_script import (
    ScriptConfig,
    load_script_config,
    resolve_audio_file,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_logger() -> logging.Logger:
    return logging.getLogger("test_auto_script")


# ---------------------------------------------------------------------------
# ScriptConfig
# ---------------------------------------------------------------------------
class TestScriptConfig:
    def test_defaults(self) -> None:
        config = ScriptConfig(base_url="https://test.com")
        assert config.base_url == "https://test.com"
        assert config.audio_dir == "downloads"
        assert config.audio_extensions == [".mp3", ".wav"]
        assert config.csv_columns["product_number"] == "No."
        assert config.csv_columns["product_name"] == "Product Name"
        assert config.csv_columns["script_content"] == "TH Script"
        assert config.csv_columns["audio_code"] == "Audio Code"


# ---------------------------------------------------------------------------
# load_script_config
# ---------------------------------------------------------------------------
class TestLoadScriptConfig:
    def test_load_valid(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.json"
        config_file.write_text('{"base_url": "https://example.com"}')
        config = load_script_config(str(config_file))
        assert config.base_url == "https://example.com"

    def test_load_missing(self) -> None:
        with pytest.raises(FileNotFoundError, match="Config file not found"):
            load_script_config("/nonexistent/config.json")

    def test_cli_override(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.json"
        config_file.write_text('{"base_url": "https://example.com"}')
        config = load_script_config(
            str(config_file), {"base_url": "https://override.com"}
        )
        assert config.base_url == "https://override.com"


# ---------------------------------------------------------------------------
# resolve_audio_file
# ---------------------------------------------------------------------------
class TestResolveAudioFile:
    def test_subfolder(self, tmp_path: Path) -> None:
        subfolder = tmp_path / "01_Product"
        subfolder.mkdir()
        audio_file = subfolder / "MJ1.mp3"
        audio_file.write_text("fake audio")

        result = resolve_audio_file(
            "MJ1", 1, str(tmp_path), [".mp3", ".wav"], _make_logger()
        )
        assert result == str(audio_file.resolve())

    def test_flat(self, tmp_path: Path) -> None:
        audio_file = tmp_path / "MJ1.mp3"
        audio_file.write_text("fake audio")

        result = resolve_audio_file(
            "MJ1", 1, str(tmp_path), [".mp3", ".wav"], _make_logger()
        )
        assert result == str(audio_file.resolve())

    def test_not_found(self, tmp_path: Path) -> None:
        result = resolve_audio_file(
            "MISSING", 1, str(tmp_path), [".mp3", ".wav"], _make_logger()
        )
        assert result is None

    def test_empty_code(self, tmp_path: Path) -> None:
        result = resolve_audio_file(
            "", 1, str(tmp_path), [".mp3", ".wav"], _make_logger()
        )
        assert result is None
