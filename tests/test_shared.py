"""Tests for shared.py utilities."""

import logging
from pathlib import Path

import pytest

from shared import (
    find_csv_file,
    load_csv,
    setup_logging,
    is_session_valid,
    get_browser_data_dir,
    set_app_support_dir,
)


# ---------------------------------------------------------------------------
# find_csv_file
# ---------------------------------------------------------------------------
class TestFindCsvFile:
    def test_explicit_path_exists(self, tmp_path: Path) -> None:
        csv_file = tmp_path / "data.csv"
        csv_file.write_text("a,b\n1,2\n")
        assert find_csv_file(str(csv_file)) == str(csv_file)

    def test_explicit_path_not_found(self) -> None:
        with pytest.raises(FileNotFoundError, match="CSV file not found"):
            find_csv_file("/nonexistent/file.csv")

    def test_auto_detect_single_csv(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        csv_file = tmp_path / "only.csv"
        csv_file.write_text("x,y\n1,2\n")
        result = find_csv_file(None)
        assert result == "only.csv"

    def test_auto_detect_no_csv(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        with pytest.raises(FileNotFoundError, match="No CSV file found"):
            find_csv_file(None)

    def test_auto_detect_multiple_csv(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "a.csv").write_text("x\n1\n")
        (tmp_path / "b.csv").write_text("y\n2\n")
        with pytest.raises(ValueError, match="Multiple CSV files found"):
            find_csv_file(None)


# ---------------------------------------------------------------------------
# load_csv
# ---------------------------------------------------------------------------
class TestLoadCsv:
    def test_load_utf8(self, tmp_path: Path) -> None:
        csv_file = tmp_path / "data.csv"
        csv_file.write_text("Name,Value\nAlice,1\nBob,2\n", encoding="utf-8")
        logger = logging.getLogger("test_load_csv")
        df = load_csv(str(csv_file), logger)
        assert len(df) == 2
        assert list(df.columns) == ["Name", "Value"]

    def test_load_cp874_fallback(self, tmp_path: Path) -> None:
        csv_file = tmp_path / "thai.csv"
        content = "ชื่อ,ค่า\nข้อมูล,1\n"
        csv_file.write_bytes(content.encode("cp874"))
        logger = logging.getLogger("test_load_csv_cp874")
        df = load_csv(str(csv_file), logger)
        assert len(df) == 1


# ---------------------------------------------------------------------------
# setup_logging
# ---------------------------------------------------------------------------
class TestSetupLogging:
    def test_creates_logger(self, tmp_path: Path) -> None:
        logger = setup_logging(
            "20260101_000000",
            logger_name="test_logger",
            log_prefix="test",
            logs_dir=str(tmp_path),
        )
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test_logger"
        # Should have console + file handlers
        assert len(logger.handlers) >= 2

    def test_log_file_created(self, tmp_path: Path) -> None:
        setup_logging(
            "20260101_120000",
            logger_name="test_logfile",
            log_prefix="myprefix",
            logs_dir=str(tmp_path),
        )
        log_files = list(tmp_path.glob("myprefix_*.log"))
        assert len(log_files) == 1

    def test_callback_handler(self, tmp_path: Path) -> None:
        messages: list[str] = []
        logger = setup_logging(
            "20260101_130000",
            logger_name="test_callback",
            log_prefix="cb",
            logs_dir=str(tmp_path),
            log_callback=messages.append,
        )
        logger.info("hello callback")
        assert any("hello callback" in m for m in messages)


# ---------------------------------------------------------------------------
# Session and directory helpers
# ---------------------------------------------------------------------------
class TestSessionHelpers:
    def test_is_session_valid_true(self, tmp_path: Path) -> None:
        session = tmp_path / "session_state.json"
        session.write_text("{}")
        set_app_support_dir(str(tmp_path))
        try:
            assert is_session_valid("session_state.json") is True
        finally:
            set_app_support_dir(None)

    def test_is_session_valid_false(self, tmp_path: Path) -> None:
        set_app_support_dir(str(tmp_path))
        try:
            assert is_session_valid("nonexistent.json") is False
        finally:
            set_app_support_dir(None)

    def test_get_browser_data_dir_default(self) -> None:
        set_app_support_dir(None)
        assert get_browser_data_dir() == "./browser_data"

    def test_get_browser_data_dir_custom_subdir(self, tmp_path: Path) -> None:
        set_app_support_dir(str(tmp_path))
        try:
            result = get_browser_data_dir("browser_data_faq")
            assert result == str(tmp_path / "browser_data_faq")
        finally:
            set_app_support_dir(None)
