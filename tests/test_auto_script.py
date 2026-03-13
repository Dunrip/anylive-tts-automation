"""Tests for auto_script.py — CSV parsing, audio resolution, config loading."""

import logging
from pathlib import Path

import pandas as pd
import pytest

from auto_script import (
    ScriptConfig,
    load_script_config,
    parse_script_csv,
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


# ---------------------------------------------------------------------------
# parse_script_csv
# ---------------------------------------------------------------------------
class TestParseScriptCsv:
    def _make_df(self, rows: list[dict]) -> pd.DataFrame:
        return pd.DataFrame(rows)

    def test_basic_grouping(self) -> None:
        """Test basic product grouping with multiple scripts per product."""
        df = self._make_df(
            [
                {
                    "No.": "1",
                    "Product Name": "Product A",
                    "TH Script": "Script 1",
                    "Audio Code": "SFD1",
                },
                {
                    "No.": "1",
                    "Product Name": "Product A",
                    "TH Script": "Script 2",
                    "Audio Code": "SFD2",
                },
                {
                    "No.": "2",
                    "Product Name": "Product B",
                    "TH Script": "Script 3",
                    "Audio Code": "SFD3",
                },
            ]
        )
        config = ScriptConfig(base_url="https://example.com")
        products = parse_script_csv(df, config, _make_logger())

        assert len(products) == 2
        assert products[0].product_number == 1
        assert products[0].product_name == "Product A"
        assert len(products[0].rows) == 2
        assert products[1].product_number == 2
        assert len(products[1].rows) == 1

    def test_forward_fill(self) -> None:
        """Product number and name should be forward-filled from previous rows."""
        df = self._make_df(
            [
                {
                    "No.": "1",
                    "Product Name": "Product A",
                    "TH Script": "Script 1",
                    "Audio Code": "SFD1",
                },
                {
                    "No.": "",
                    "Product Name": "",
                    "TH Script": "Script 2",
                    "Audio Code": "SFD2",
                },
                {
                    "No.": "2",
                    "Product Name": "Product B",
                    "TH Script": "Script 3",
                    "Audio Code": "SFD3",
                },
            ]
        )
        config = ScriptConfig(base_url="https://example.com")
        products = parse_script_csv(df, config, _make_logger())

        assert len(products) == 2
        assert products[0].product_number == 1
        assert len(products[0].rows) == 2
        assert products[0].rows[1].script_content == "Script 2"

    def test_header_detection(self) -> None:
        """Headers in first data row should be auto-detected."""
        df = self._make_df(
            [
                {
                    "No.": "No.",
                    "Product Name": "Product Name",
                    "TH Script": "TH Script",
                    "Audio Code": "Audio Code",
                },
                {
                    "No.": "1",
                    "Product Name": "Product A",
                    "TH Script": "Script 1",
                    "Audio Code": "SFD1",
                },
            ]
        )
        config = ScriptConfig(base_url="https://example.com")
        products = parse_script_csv(df, config, _make_logger())

        assert len(products) == 1
        assert products[0].product_number == 1
        assert len(products[0].rows) == 1

    def test_empty_rows_filtered(self) -> None:
        """Rows without script_content AND audio_code should be excluded."""
        df = self._make_df(
            [
                {
                    "No.": "1",
                    "Product Name": "Product A",
                    "TH Script": "Script 1",
                    "Audio Code": "SFD1",
                },
                {
                    "No.": "1",
                    "Product Name": "Product A",
                    "TH Script": None,
                    "Audio Code": None,
                },
                {
                    "No.": "1",
                    "Product Name": "Product A",
                    "TH Script": "Script 2",
                    "Audio Code": "SFD2",
                },
            ]
        )
        config = ScriptConfig(base_url="https://example.com")
        products = parse_script_csv(df, config, _make_logger())

        assert len(products) == 1
        assert len(products[0].rows) == 2

    def test_product_zero_filtered(self) -> None:
        """Product number < 1 should be filtered out and logged."""
        df = self._make_df(
            [
                {
                    "No.": "0",
                    "Product Name": "Product Zero",
                    "TH Script": "Script 0",
                    "Audio Code": "SFD0",
                },
                {
                    "No.": "1",
                    "Product Name": "Product A",
                    "TH Script": "Script 1",
                    "Audio Code": "SFD1",
                },
            ]
        )
        config = ScriptConfig(base_url="https://example.com")
        products = parse_script_csv(df, config, _make_logger())

        assert len(products) == 1
        assert products[0].product_number == 1

    def test_empty_df(self) -> None:
        """Empty DataFrame should return empty list."""
        df = self._make_df([])
        config = ScriptConfig(base_url="https://example.com")
        products = parse_script_csv(df, config, _make_logger())

        assert len(products) == 0
