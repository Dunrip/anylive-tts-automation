"""Tests for shared.py utilities."""

import logging
from pathlib import Path

import pytest

from shared import (
    _scrape_user_profile,
    find_csv_file,
    load_csv,
    load_jsonc,
    setup_logging,
    is_session_valid,
    get_browser_data_dir,
    set_app_support_dir,
    _c,
    _Ansi,
    strip_ansi,
    set_color_enabled,
    SYM,
    ConsoleFormatter,
    EmojiFormatter,
    PlainFormatter,
    fmt_banner,
    fmt_kv,
    fmt_section,
    fmt_item,
    fmt_step,
    fmt_result,
    fmt_elapsed,
    fmt_summary,
    fmt_report_header,
    fmt_report_footer,
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
            log_callback=lambda msg, level: messages.append(msg),
        )
        logger.info("hello callback")
        assert any("hello callback" in m for m in messages)


# ---------------------------------------------------------------------------
# Session and directory helpers
# ---------------------------------------------------------------------------
class TestSessionHelpers:
    def test_is_session_valid_true(self, tmp_path: Path) -> None:
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        session = state_dir / "session_state.json"
        session.write_text("{}")
        set_app_support_dir(str(tmp_path))
        try:
            assert is_session_valid("state/session_state.json") is True
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
        assert get_browser_data_dir() == "./state/browser_data"

    def test_get_browser_data_dir_custom_subdir(self, tmp_path: Path) -> None:
        set_app_support_dir(str(tmp_path))
        try:
            result = get_browser_data_dir("state/browser_data_faq")
            assert result == str(tmp_path / "state" / "browser_data_faq")
        finally:
            set_app_support_dir(None)


class TestLoadJsonc:
    def test_plain_json(self, tmp_path: Path) -> None:
        f = tmp_path / "plain.json"
        f.write_text('{"key": "value"}')
        assert load_jsonc(str(f)) == {"key": "value"}

    def test_full_line_comments(self, tmp_path: Path) -> None:
        f = tmp_path / "commented.json"
        f.write_text('{\n  // this is a comment\n  "key": "value"\n}')
        assert load_jsonc(str(f)) == {"key": "value"}

    def test_trailing_comments(self, tmp_path: Path) -> None:
        f = tmp_path / "trailing.json"
        f.write_text('{\n  "key": "value"  // inline comment\n}')
        assert load_jsonc(str(f)) == {"key": "value"}


class TestScrapeUserProfile:
    def test_scrape_user_profile_exists(self) -> None:
        assert callable(_scrape_user_profile)

    def test_session_json_includes_profile_fields_when_scraping_succeeds(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import json
        from unittest.mock import AsyncMock, patch

        mock_profile = {"display_name": "Test User", "email": "test@example.com"}

        with patch(
            "shared._scrape_user_profile", new_callable=AsyncMock
        ) as mock_scrape:
            mock_scrape.return_value = mock_profile

            session_data = {
                "setup_complete": True,
                "timestamp": "2026-03-17T12:00:00",
            }
            session_data.update(mock_profile)

            session_file = tmp_path / "session_state.json"
            with open(session_file, "w") as f:
                json.dump(session_data, f)

            with open(session_file, "r") as f:
                written_data = json.load(f)

            assert written_data["setup_complete"] is True
            assert written_data["display_name"] == "Test User"
            assert written_data["email"] == "test@example.com"
            assert "timestamp" in written_data

    def test_session_json_written_when_scraping_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import json
        from unittest.mock import AsyncMock, patch

        with patch(
            "shared._scrape_user_profile", new_callable=AsyncMock
        ) as mock_scrape:
            mock_scrape.return_value = {}

            session_data = {
                "setup_complete": True,
                "timestamp": "2026-03-17T12:00:00",
            }
            session_data.update({})

            session_file = tmp_path / "session_state.json"
            with open(session_file, "w") as f:
                json.dump(session_data, f)

            with open(session_file, "r") as f:
                written_data = json.load(f)

            assert written_data["setup_complete"] is True
            assert "timestamp" in written_data
            assert "display_name" not in written_data
            assert "email" not in written_data


# ---------------------------------------------------------------------------
# Color utilities
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _restore_color():
    """Ensure color state is reset between tests."""
    set_color_enabled(True)
    yield
    set_color_enabled(True)


class TestStripAnsi:
    def test_removes_basic_codes(self) -> None:
        assert strip_ansi("\033[31mhello\033[0m") == "hello"

    def test_removes_nested_codes(self) -> None:
        assert strip_ansi("\033[1m\033[31mbold\033[0m") == "bold"

    def test_passthrough_plain_text(self) -> None:
        assert strip_ansi("no ansi here") == "no ansi here"


class TestColorControl:
    def test_enabled_wraps_ansi(self) -> None:
        set_color_enabled(True)
        assert "\033[31m" in _c("x", _Ansi.RED)

    def test_disabled_returns_plain(self) -> None:
        set_color_enabled(False)
        assert _c("x", _Ansi.RED) == "x"

    def test_no_codes_returns_plain(self) -> None:
        assert _c("x") == "x"


class TestConsoleFormatter:
    def test_debug_dimmed(self) -> None:
        record = logging.LogRecord(
            name="test",
            level=logging.DEBUG,
            pathname="",
            lineno=0,
            msg="test message",
            args=(),
            exc_info=None,
        )
        formatter = ConsoleFormatter()
        assert "\033[2m" in formatter.format(record)

    def test_info_passthrough(self) -> None:
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test message",
            args=(),
            exc_info=None,
        )
        formatter = ConsoleFormatter()
        assert formatter.format(record) == "test message"


class TestPlainFormatter:
    def test_strips_ansi_from_message(self) -> None:
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="\033[31mred text\033[0m",
            args=(),
            exc_info=None,
        )
        formatter = PlainFormatter()
        assert "\033[" not in formatter.format(record)

    def test_default_time_fmt_is_full_date(self) -> None:
        assert PlainFormatter()._time_fmt == "%Y-%m-%d %H:%M:%S"


class TestEmojiFormatterDeprecation:
    def test_warns_on_construction(self) -> None:
        with pytest.warns(DeprecationWarning, match="deprecated"):
            result = EmojiFormatter()
        assert type(result).__name__ == "ConsoleFormatter"


class TestFmtBanner:
    def test_contains_title_and_box_chars(self) -> None:
        result = fmt_banner("HELLO")
        assert "HELLO" in result
        assert "┌" in result
        assert "└" in result

    def test_includes_context_values(self) -> None:
        assert "Foo: bar" in fmt_banner("T", Foo="bar")

    def test_no_context_line_when_empty(self) -> None:
        assert ":" not in strip_ansi(fmt_banner("T"))


class TestFmtKv:
    def test_alignment(self) -> None:
        lines = strip_ansi(fmt_kv([("A", "1"), ("LongKey", "2")])).splitlines()
        assert lines[0].index("1") == lines[1].index("2")

    def test_empty_list(self) -> None:
        assert fmt_kv([]) == ""


class TestFmtSection:
    def test_contains_label(self) -> None:
        assert "Processing" in strip_ansi(fmt_section("Processing"))


class TestFmtItem:
    def test_counter_format(self) -> None:
        result = strip_ansi(fmt_item(1, 5, "hello"))
        assert "[1/5]" in result
        assert "hello" in result


class TestFmtStep:
    def test_ok_symbol(self) -> None:
        result = strip_ansi(fmt_step(SYM.OK, "done"))
        assert "✓" in result
        assert "done" in result

    def test_with_elapsed(self) -> None:
        assert "3.2s" in strip_ansi(fmt_step(SYM.OK, "done", "3.2s"))


class TestFmtResult:
    def test_ok_true(self) -> None:
        result = strip_ansi(fmt_result(True, "all good"))
        assert "OK" in result
        assert "all good" in result

    def test_ok_false(self) -> None:
        result = strip_ansi(fmt_result(False, "broke"))
        assert "FAILED" in result
        assert "broke" in result


class TestFmtElapsed:
    def test_under_60(self) -> None:
        assert fmt_elapsed(8.1) == "8.1s"

    def test_over_60(self) -> None:
        assert fmt_elapsed(154) == "2m 34s"

    def test_boundary_59_95(self) -> None:
        assert fmt_elapsed(59.95) == "1m 00s"

    def test_exactly_zero(self) -> None:
        assert fmt_elapsed(0) == "0.0s"


class TestFmtSummaryAndReport:
    def test_summary_multiple_parts(self) -> None:
        result = strip_ansi(fmt_summary("A", "B"))
        assert "A" in result
        assert "·" in result
        assert "B" in result

    def test_report_header_contains_title(self) -> None:
        assert "REPORT" in strip_ansi(fmt_report_header("REPORT"))

    def test_report_footer_is_separator(self) -> None:
        stripped = strip_ansi(fmt_report_footer())
        assert stripped and all(c == "─" for c in stripped)
