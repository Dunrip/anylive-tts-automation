"""Tests for auto_script.py — CSV parsing, audio resolution, config loading."""

import logging
from pathlib import Path

import pandas as pd
import pytest

from auto_script import (
    ProductScript,
    ScriptConfig,
    _normalize_script_name,
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
# _normalize_script_name
# ---------------------------------------------------------------------------
class TestNormalizeScriptName:
    def test_mp3_extension(self) -> None:
        assert _normalize_script_name("SFD1.mp3") == "sfd1"

    def test_wav_extension(self) -> None:
        assert _normalize_script_name("SFD1.wav") == "sfd1"

    def test_no_extension(self) -> None:
        assert _normalize_script_name("SFD1") == "sfd1"

    def test_whitespace_and_extension(self) -> None:
        assert _normalize_script_name("  SFD1.mp3  ") == "sfd1"

    def test_uppercase_extension(self) -> None:
        assert _normalize_script_name("sfd1.MP3") == "sfd1"

    def test_empty_string(self) -> None:
        assert _normalize_script_name("") == ""

    def test_multiple_dots(self) -> None:
        assert _normalize_script_name("file.with.dots.mp3") == "file.with.dots"


# ---------------------------------------------------------------------------
# Upload filtering logic
# ---------------------------------------------------------------------------
class TestUploadFiltering:
    def test_all_present_filters_everything(self) -> None:
        existing = ["SFD1.mp3", "SFD2.mp3"]
        csv_codes = ["SFD1", "SFD2"]
        existing_normalized = {_normalize_script_name(n) for n in existing}
        filtered = [
            c for c in csv_codes if _normalize_script_name(c) not in existing_normalized
        ]
        assert filtered == []

    def test_partial_present_filters_matches(self) -> None:
        existing = ["SFD1.mp3"]
        csv_codes = ["SFD1", "SFD2", "SFD3"]
        existing_normalized = {_normalize_script_name(n) for n in existing}
        filtered = [
            c for c in csv_codes if _normalize_script_name(c) not in existing_normalized
        ]
        assert filtered == ["SFD2", "SFD3"]

    def test_none_present_filters_nothing(self) -> None:
        existing: list[str] = []
        csv_codes = ["SFD1", "SFD2", "SFD3"]
        existing_normalized = {_normalize_script_name(n) for n in existing}
        filtered = [
            c for c in csv_codes if _normalize_script_name(c) not in existing_normalized
        ]
        assert filtered == ["SFD1", "SFD2", "SFD3"]

    def test_case_insensitive_matching(self) -> None:
        existing = ["sfd1.MP3"]
        csv_codes = ["SFD1"]
        existing_normalized = {_normalize_script_name(n) for n in existing}
        filtered = [
            c for c in csv_codes if _normalize_script_name(c) not in existing_normalized
        ]
        assert filtered == []

    def test_overflow_with_filtered_count(self) -> None:
        current_count = 18
        existing = ["SFD1.mp3", "SFD2.mp3", "SFD3.mp3"]
        csv_codes = ["SFD1", "SFD2", "SFD3", "SFD4", "SFD5"]
        existing_normalized = {_normalize_script_name(n) for n in existing}
        filtered = [
            c for c in csv_codes if _normalize_script_name(c) not in existing_normalized
        ]
        assert len(filtered) == 2
        assert current_count + len(filtered) <= 20

    def test_report_includes_scripts_skipped(self) -> None:
        """Report dict should include scripts_skipped field for each product."""
        p = ProductScript(product_number=1, product_name="Test", scripts_skipped=3)
        assert p.scripts_skipped == 3


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

    def test_parse_script_csv_custom_columns(self) -> None:
        """Custom csv_columns mapping should be respected."""
        df = self._make_df(
            [
                {
                    "Num": "1",
                    "Name": "Product A",
                    "Script": "Script 1",
                    "Code": "SFD1",
                }
            ]
        )
        config = ScriptConfig(
            base_url="https://example.com",
            csv_columns={
                "product_number": "Num",
                "product_name": "Name",
                "script_content": "Script",
                "audio_code": "Code",
            },
        )
        products = parse_script_csv(df, config, _make_logger())

        assert len(products) == 1
        assert products[0].product_number == 1
        assert products[0].rows[0].script_content == "Script 1"
        assert products[0].rows[0].audio_code == "SFD1"
