"""Tests for sidecar Pydantic models."""

from __future__ import annotations


from models.config import CSVColumns, LiveConfig, SessionStatus, TTSConfig
from models.job import (
    AutomationOptions,
    AutomationType,
    JobProgress,
    JobStartRequest,
    JobStatus,
    JobStatusResponse,
)
from models.messages import LogLevel, LogMessage, ProgressMessage, StatusMessage


class TestJobModels:
    def test_job_status_enum(self) -> None:
        assert JobStatus.PENDING == "pending"
        assert JobStatus.SUCCESS == "success"
        assert JobStatus.FAILED == "failed"

    def test_automation_options_defaults(self) -> None:
        opts = AutomationOptions()
        assert opts.headless is False
        assert opts.dry_run is False
        assert opts.debug is False
        assert opts.delete_scripts is False

    def test_job_start_request_required_fields(self) -> None:
        req = JobStartRequest(
            automation_type=AutomationType.TTS,
            config_path="/path/to/config.json",
        )
        assert req.automation_type == "tts"
        assert req.csv_path is None

    def test_job_start_request_with_csv(self) -> None:
        req = JobStartRequest(
            automation_type=AutomationType.TTS,
            config_path="/config.json",
            csv_path="/data.csv",
        )
        assert req.csv_path == "/data.csv"

    def test_job_status_response(self) -> None:
        resp = JobStatusResponse(
            job_id="job-123",
            status=JobStatus.RUNNING,
            progress=JobProgress(current=2, total=10),
            started_at="2026-01-01T00:00:00Z",
        )
        assert resp.status == "running"
        assert resp.progress.total == 10


class TestConfigModels:
    def test_tts_config_required_fields(self) -> None:
        config = TTSConfig(
            base_url="https://example.com",
            version_template="Template",
            voice_name="Voice",
        )
        assert config.max_scripts_per_version == 10
        assert config.enable_voice_selection is False

    def test_csv_columns_defaults(self) -> None:
        cols = CSVColumns()
        assert cols.product_number == "No."
        assert cols.product_name == "Product Name"

    def test_live_config_defaults(self) -> None:
        config = LiveConfig()
        assert config.audio_dir is None
        assert config.audio_extensions == [".mp3", ".wav"]

    def test_session_status(self) -> None:
        status = SessionStatus(
            valid=True,
            site="tts",
            client="default",
            checked_at="2026-01-01T00:00:00Z",
        )
        assert status.valid is True
        assert status.site == "tts"


class TestMessageModels:
    def test_log_message(self) -> None:
        msg = LogMessage(
            level=LogLevel.INFO,
            message="Processing version 1",
            timestamp="2026-01-01T00:00:00Z",
        )
        assert msg.type == "log"
        assert msg.level == "INFO"

    def test_progress_message(self) -> None:
        msg = ProgressMessage(current=3, total=10, version_name="1_ProductA")
        assert msg.type == "progress"
        assert msg.current == 3

    def test_status_message(self) -> None:
        msg = StatusMessage(job_id="job-123", status="success")
        assert msg.type == "status"
