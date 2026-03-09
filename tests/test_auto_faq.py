"""Tests for auto_faq.py — CSV parsing, audio resolution, config loading."""

import logging
from pathlib import Path

import pandas as pd
import pytest

from auto_faq import (
    FAQConfig,
    load_faq_config,
    parse_faq_csv,
    resolve_audio_file,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_logger() -> logging.Logger:
    return logging.getLogger("test_auto_faq")


def _make_df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# parse_faq_csv
# ---------------------------------------------------------------------------
class TestParseFaqCsv:
    def test_basic_grouping(self) -> None:
        df = _make_df(
            [
                {
                    "No.": "1",
                    "Product Name": "Product A",
                    "Question": "Q1?",
                    "Audio Code": "SFD1",
                },
                {
                    "No.": "1",
                    "Product Name": "Product A",
                    "Question": "Q2?",
                    "Audio Code": "SFD2",
                },
                {
                    "No.": "2",
                    "Product Name": "Product B",
                    "Question": "Q3?",
                    "Audio Code": "SFD3",
                },
            ]
        )
        config = FAQConfig(base_url="https://example.com")
        products = parse_faq_csv(df, config, _make_logger())

        assert len(products) == 2
        assert products[0].product_number == 1
        assert products[0].product_name == "Product A"
        assert len(products[0].rows) == 2
        assert products[1].product_number == 2
        assert len(products[1].rows) == 1

    def test_forward_fill(self) -> None:
        """Product number and name should be forward-filled from previous rows."""
        df = _make_df(
            [
                {
                    "No.": "1",
                    "Product Name": "Product A",
                    "Question": "Q1?",
                    "Audio Code": "SFD1",
                },
                {
                    "No.": "",
                    "Product Name": "",
                    "Question": "Q2?",
                    "Audio Code": "SFD2",
                },
                {
                    "No.": "2",
                    "Product Name": "Product B",
                    "Question": "Q3?",
                    "Audio Code": "SFD3",
                },
            ]
        )
        config = FAQConfig(base_url="https://example.com")
        products = parse_faq_csv(df, config, _make_logger())

        assert len(products) == 2
        assert products[0].product_number == 1
        assert len(products[0].rows) == 2
        assert products[0].rows[1].question == "Q2?"

    def test_empty_rows_filtered(self) -> None:
        """Rows without question or audio code should be excluded."""
        df = _make_df(
            [
                {
                    "No.": "1",
                    "Product Name": "Product A",
                    "Question": "Q1?",
                    "Audio Code": "SFD1",
                },
                {
                    "No.": "1",
                    "Product Name": "Product A",
                    "Question": None,
                    "Audio Code": None,
                },
                {
                    "No.": "1",
                    "Product Name": "Product A",
                    "Question": "Q2?",
                    "Audio Code": "SFD2",
                },
            ]
        )
        config = FAQConfig(base_url="https://example.com")
        products = parse_faq_csv(df, config, _make_logger())

        assert len(products) == 1
        assert len(products[0].rows) == 2

    def test_float_product_number(self) -> None:
        """Product numbers like '1.0' should be parsed as int 1."""
        df = _make_df(
            [
                {
                    "No.": "1.0",
                    "Product Name": "Product A",
                    "Question": "Q1?",
                    "Audio Code": "SFD1",
                },
            ]
        )
        config = FAQConfig(base_url="https://example.com")
        products = parse_faq_csv(df, config, _make_logger())

        assert products[0].product_number == 1

    def test_custom_csv_columns(self) -> None:
        """Config can specify custom column names."""
        df = _make_df(
            [
                {"Num": "1", "Name": "Prod A", "Q": "Q1?", "Code": "SFD1"},
            ]
        )
        config = FAQConfig(
            base_url="https://example.com",
            csv_columns={
                "product_number": "Num",
                "product_name": "Name",
                "question": "Q",
                "audio_code": "Code",
            },
        )
        products = parse_faq_csv(df, config, _make_logger())

        assert len(products) == 1
        assert products[0].rows[0].question == "Q1?"

    def test_sorted_by_product_number(self) -> None:
        """Products should be sorted by product number."""
        df = _make_df(
            [
                {"No.": "3", "Product Name": "C", "Question": "Q?", "Audio Code": "X"},
                {"No.": "1", "Product Name": "A", "Question": "Q?", "Audio Code": "Y"},
            ]
        )
        config = FAQConfig(base_url="https://example.com")
        products = parse_faq_csv(df, config, _make_logger())

        assert products[0].product_number == 1
        assert products[1].product_number == 3


# ---------------------------------------------------------------------------
# resolve_audio_file
# ---------------------------------------------------------------------------
class TestResolveAudioFile:
    def test_subfolder_match(self, tmp_path: Path) -> None:
        """Find audio in zero-padded subfolder."""
        subfolder = tmp_path / "01_Product_A"
        subfolder.mkdir()
        audio_file = subfolder / "SFD1.mp3"
        audio_file.write_text("fake audio")

        result = resolve_audio_file(
            "SFD1", 1, str(tmp_path), [".mp3", ".wav"], _make_logger()
        )
        assert result == str(audio_file.resolve())

    def test_flat_fallback(self, tmp_path: Path) -> None:
        """Find audio in flat directory root when no subfolder matches."""
        audio_file = tmp_path / "SFD1.mp3"
        audio_file.write_text("fake audio")

        result = resolve_audio_file(
            "SFD1", 1, str(tmp_path), [".mp3", ".wav"], _make_logger()
        )
        assert result == str(audio_file.resolve())

    def test_wav_extension(self, tmp_path: Path) -> None:
        """Should find .wav files too."""
        subfolder = tmp_path / "02_Product_B"
        subfolder.mkdir()
        audio_file = subfolder / "SFD2.wav"
        audio_file.write_text("fake audio")

        result = resolve_audio_file(
            "SFD2", 2, str(tmp_path), [".mp3", ".wav"], _make_logger()
        )
        assert result == str(audio_file.resolve())

    def test_not_found_returns_none(self, tmp_path: Path) -> None:
        result = resolve_audio_file(
            "MISSING", 1, str(tmp_path), [".mp3", ".wav"], _make_logger()
        )
        assert result is None

    def test_empty_audio_code_returns_none(self, tmp_path: Path) -> None:
        result = resolve_audio_file(
            "", 1, str(tmp_path), [".mp3", ".wav"], _make_logger()
        )
        assert result is None

    def test_nonexistent_audio_dir(self) -> None:
        result = resolve_audio_file(
            "SFD1", 1, "/nonexistent/dir", [".mp3"], _make_logger()
        )
        assert result is None

    def test_zero_padding(self, tmp_path: Path) -> None:
        """Product 5 should match folder '05_...'."""
        subfolder = tmp_path / "05_Product_E"
        subfolder.mkdir()
        audio_file = subfolder / "SFD5.mp3"
        audio_file.write_text("fake audio")

        result = resolve_audio_file("SFD5", 5, str(tmp_path), [".mp3"], _make_logger())
        assert result == str(audio_file.resolve())


# ---------------------------------------------------------------------------
# load_faq_config
# ---------------------------------------------------------------------------
class TestLoadFaqConfig:
    def test_load_basic(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.json"
        config_file.write_text(
            '{"base_url": "https://example.com", "audio_dir": "my_audio"}'
        )
        config = load_faq_config(str(config_file))
        assert config.base_url == "https://example.com"
        assert config.audio_dir == "my_audio"

    def test_cli_overrides(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.json"
        config_file.write_text('{"base_url": "https://example.com"}')
        config = load_faq_config(str(config_file), {"audio_dir": "override_dir"})
        assert config.audio_dir == "override_dir"

    def test_not_found(self) -> None:
        with pytest.raises(FileNotFoundError, match="Config file not found"):
            load_faq_config("/nonexistent/config.json")

    def test_default_values(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.json"
        config_file.write_text('{"base_url": "https://example.com"}')
        config = load_faq_config(str(config_file))
        assert config.audio_dir == "downloads"
        assert config.audio_extensions == [".mp3", ".wav"]


# ---------------------------------------------------------------------------
# Product number matching (int comparison)
# ---------------------------------------------------------------------------
class TestProductNumberMatching:
    def test_int_comparison(self) -> None:
        """CSV product number (as string '1') should match website label (int 1)."""
        df = _make_df(
            [
                {"No.": "1", "Product Name": "P", "Question": "Q?", "Audio Code": "A"},
            ]
        )
        config = FAQConfig(base_url="https://example.com")
        products = parse_faq_csv(df, config, _make_logger())

        assert products[0].product_number == 1  # int, not string
        assert isinstance(products[0].product_number, int)

    def test_string_number_to_int(self) -> None:
        """Various string representations should all become int."""
        df = _make_df(
            [
                {
                    "No.": "01",
                    "Product Name": "P1",
                    "Question": "Q?",
                    "Audio Code": "A",
                },
                {
                    "No.": "2.0",
                    "Product Name": "P2",
                    "Question": "Q?",
                    "Audio Code": "B",
                },
                {
                    "No.": "10",
                    "Product Name": "P3",
                    "Question": "Q?",
                    "Audio Code": "C",
                },
            ]
        )
        config = FAQConfig(base_url="https://example.com")
        products = parse_faq_csv(df, config, _make_logger())

        assert [p.product_number for p in products] == [1, 2, 10]
