"""Tests for auto_tts utility functions."""

import logging
from pathlib import Path

import pandas as pd
import pytest

from auto_tts import (
    ClientConfig,
    parse_version_spec,
    _extract_leading_number,
    collect_expected_audio_codes,
    verify_downloads,
)


class TestParseVersionSpec:
    """Tests for parse_version_spec()."""

    def test_single_number(self) -> None:
        assert parse_version_spec("15") == {15}

    def test_multiple_numbers(self) -> None:
        assert parse_version_spec("15,18,24") == {15, 18, 24}

    def test_range(self) -> None:
        assert parse_version_spec("15-18") == {15, 16, 17, 18}

    def test_mixed_numbers_and_ranges(self) -> None:
        assert parse_version_spec("15-18,24,30") == {15, 16, 17, 18, 24, 30}

    def test_overlapping_ranges(self) -> None:
        assert parse_version_spec("1-5,3-7") == {1, 2, 3, 4, 5, 6, 7}

    def test_single_number_range(self) -> None:
        assert parse_version_spec("5-5") == {5}

    def test_whitespace_tolerance(self) -> None:
        assert parse_version_spec(" 15 - 18 , 24 ") == {15, 16, 17, 18, 24}

    def test_leading_trailing_whitespace(self) -> None:
        assert parse_version_spec("  10  ") == {10}

    def test_error_empty_string(self) -> None:
        with pytest.raises(ValueError, match="cannot be empty"):
            parse_version_spec("")

    def test_error_whitespace_only(self) -> None:
        with pytest.raises(ValueError, match="cannot be empty"):
            parse_version_spec("   ")

    def test_error_non_numeric(self) -> None:
        with pytest.raises(ValueError, match="Non-numeric"):
            parse_version_spec("abc")

    def test_error_non_numeric_in_range(self) -> None:
        with pytest.raises(ValueError, match="Non-numeric value in range"):
            parse_version_spec("1-abc")

    def test_error_reversed_range(self) -> None:
        with pytest.raises(ValueError, match="Reversed range"):
            parse_version_spec("18-15")

    def test_error_trailing_comma(self) -> None:
        with pytest.raises(ValueError, match="trailing or double comma"):
            parse_version_spec("15,18,")

    def test_error_double_comma(self) -> None:
        with pytest.raises(ValueError, match="trailing or double comma"):
            parse_version_spec("15,,18")

    def test_large_range(self) -> None:
        result = parse_version_spec("1-100")
        assert result == set(range(1, 101))
        assert len(result) == 100


class TestExtractLeadingNumber:
    """Tests for _extract_leading_number()."""

    def test_standard_version_name(self) -> None:
        assert _extract_leading_number("15_ProductA") == 15

    def test_zero_padded(self) -> None:
        assert _extract_leading_number("01_Product") == 1

    def test_decimal_product_number(self) -> None:
        # "10.5_ProductA" extracts leading integer 10
        assert _extract_leading_number("10.5_ProductA") == 10

    def test_no_leading_number(self) -> None:
        assert _extract_leading_number("Template_Version") is None

    def test_number_only(self) -> None:
        assert _extract_leading_number("42") == 42

    def test_empty_string(self) -> None:
        assert _extract_leading_number("") is None


def _make_config(**overrides: object) -> ClientConfig:
    """Create a minimal ClientConfig for testing."""
    defaults = {
        "base_url": "https://example.com",
        "version_template": "Template",
        "voice_name": "Voice",
        "max_scripts_per_version": 10,
        "enable_voice_selection": False,
        "enable_product_info": False,
        "csv_columns": {
            "product_number": "No",
            "product_name": "Product Name",
            "script_content": "TH Script",
            "audio_code": "Audio Code",
        },
    }
    defaults.update(overrides)
    return ClientConfig(**defaults)


class TestCollectExpectedAudioCodes:
    """Tests for collect_expected_audio_codes()."""

    @pytest.fixture()
    def logger(self) -> logging.Logger:
        return logging.getLogger("test_collect")

    def test_basic_extraction(self, logger: logging.Logger) -> None:
        df = pd.DataFrame({"Audio Code": ["NCE1", "NCE2", "SCE1"]})
        result = collect_expected_audio_codes(df, _make_config(), logger)
        assert result == {"NCE1", "NCE2", "SCE1"}

    def test_filters_empty_and_nan(self, logger: logging.Logger) -> None:
        df = pd.DataFrame({"Audio Code": ["NCE1", "", None, "  ", "NCE2"]})
        result = collect_expected_audio_codes(df, _make_config(), logger)
        assert result == {"NCE1", "NCE2"}

    def test_deduplicates(self, logger: logging.Logger) -> None:
        df = pd.DataFrame({"Audio Code": ["NCE1", "NCE1", "NCE2"]})
        result = collect_expected_audio_codes(df, _make_config(), logger)
        assert result == {"NCE1", "NCE2"}

    def test_missing_column_returns_empty(self, logger: logging.Logger) -> None:
        df = pd.DataFrame({"Other Column": ["A", "B"]})
        result = collect_expected_audio_codes(df, _make_config(), logger)
        assert result == set()

    def test_custom_column_name(self, logger: logging.Logger) -> None:
        config = _make_config(
            csv_columns={
                "product_number": "No",
                "product_name": "Product Name",
                "script_content": "TH Script",
                "audio_code": "Code",
            }
        )
        df = pd.DataFrame({"Code": ["X1", "X2"]})
        result = collect_expected_audio_codes(df, config, logger)
        assert result == {"X1", "X2"}

    def test_product_filter(self, logger: logging.Logger) -> None:
        df = pd.DataFrame(
            {
                "No": [0, 0, 11, 11, 12, 25],
                "Audio Code": ["NCE1", "NCE2", "SCE1", "SCE2", "SCE3", "XCE1"],
            }
        )
        result = collect_expected_audio_codes(
            df, _make_config(), logger, product_filter={0, 11}
        )
        assert result == {"NCE1", "NCE2", "SCE1", "SCE2"}

    def test_product_filter_with_forward_fill(self, logger: logging.Logger) -> None:
        df = pd.DataFrame(
            {
                "No": [1, None, None, 2, None],
                "Audio Code": ["A1", "A2", "A3", "B1", "B2"],
            }
        )
        result = collect_expected_audio_codes(
            df, _make_config(), logger, product_filter={1}
        )
        assert result == {"A1", "A2", "A3"}


class TestVerifyDownloads:
    """Tests for verify_downloads()."""

    @pytest.fixture()
    def logger(self) -> logging.Logger:
        return logging.getLogger("test_verify")

    def test_all_present(self, tmp_path: Path, logger: logging.Logger) -> None:
        sub = tmp_path / "01_Product"
        sub.mkdir()
        for code in ["NCE1", "NCE2", "NCE3"]:
            (sub / f"{code}.mp3").touch()

        result = verify_downloads(str(tmp_path), {"NCE1", "NCE2", "NCE3"}, logger)
        assert result == []

    def test_true_missing(self, tmp_path: Path, logger: logging.Logger) -> None:
        sub = tmp_path / "01_Product"
        sub.mkdir()
        (sub / "NCE1.mp3").touch()
        (sub / "NCE3.mp3").touch()

        result = verify_downloads(str(tmp_path), {"NCE1", "NCE2", "NCE3"}, logger)
        assert result == ["NCE2"]

    def test_extra_files_ok(self, tmp_path: Path, logger: logging.Logger) -> None:
        sub = tmp_path / "01_Product"
        sub.mkdir()
        (sub / "NCE1.mp3").touch()
        (sub / "NCE2.mp3").touch()  # extra, not in expected

        result = verify_downloads(str(tmp_path), {"NCE1"}, logger)
        assert result == []

    def test_empty_expected(self, tmp_path: Path, logger: logging.Logger) -> None:
        sub = tmp_path / "data"
        sub.mkdir()
        (sub / "NCE1.mp3").touch()

        result = verify_downloads(str(tmp_path), set(), logger)
        assert result == []

    def test_empty_directory(self, tmp_path: Path, logger: logging.Logger) -> None:
        result = verify_downloads(str(tmp_path), {"NCE1"}, logger)
        assert result == ["NCE1"]

    def test_csv_gaps_not_reported(
        self, tmp_path: Path, logger: logging.Logger
    ) -> None:
        """Non-sequential codes in CSV are fine — only truly missing ones flagged."""
        sub = tmp_path / "downloads"
        sub.mkdir()
        for code in ["NCE1", "NCE3", "NCE5"]:
            (sub / f"{code}.mp3").touch()

        result = verify_downloads(str(sub), {"NCE1", "NCE3", "NCE5"}, logger)
        assert result == []

    def test_files_across_subdirectories(
        self, tmp_path: Path, logger: logging.Logger
    ) -> None:
        sub1 = tmp_path / "01_A"
        sub1.mkdir()
        (sub1 / "NCE1.mp3").touch()

        sub2 = tmp_path / "02_B"
        sub2.mkdir()
        (sub2 / "SCE1.mp3").touch()

        result = verify_downloads(str(tmp_path), {"NCE1", "SCE1", "SCE2"}, logger)
        assert result == ["SCE2"]

    def test_different_extensions_matched(
        self, tmp_path: Path, logger: logging.Logger
    ) -> None:
        (tmp_path / "NCE1.wav").touch()
        (tmp_path / "NCE2.mp3").touch()

        result = verify_downloads(str(tmp_path), {"NCE1", "NCE2"}, logger)
        assert result == []
