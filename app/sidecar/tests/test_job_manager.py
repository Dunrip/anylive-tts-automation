from __future__ import annotations

from models.job import AutomationType, JobStatus
from services.job_manager import JobManager


class TestJobManager:
    def setup_method(self) -> None:
        self.manager = JobManager()

    def test_create_job_returns_job(self) -> None:
        job = self.manager.create_job(
            automation_type=AutomationType.TTS,
            config_path="/config.json",
            csv_path="/data.csv",
            options={},
        )
        assert job.job_id
        assert job.status == JobStatus.PENDING

    def test_create_second_job_raises_when_running(self) -> None:
        job = self.manager.create_job(
            automation_type=AutomationType.TTS,
            config_path="/config.json",
            csv_path="/data.csv",
            options={},
        )
        job.status = JobStatus.RUNNING

        try:
            self.manager.create_job(
                automation_type=AutomationType.FAQ,
                config_path="/config.json",
                csv_path="/data.csv",
                options={},
            )
            assert False, "expected ValueError"
        except ValueError as exc:
            assert "already running" in str(exc)

    def test_get_job_returns_job(self) -> None:
        job = self.manager.create_job(
            automation_type=AutomationType.TTS,
            config_path="/config.json",
            csv_path=None,
            options={},
        )
        retrieved = self.manager.get_job(job.job_id)
        assert retrieved is job

    def test_get_nonexistent_job_returns_none(self) -> None:
        assert self.manager.get_job("nonexistent-id") is None

    async def test_run_job_transitions_to_success(self) -> None:
        job = self.manager.create_job(
            automation_type=AutomationType.TTS,
            config_path="/config.json",
            csv_path=None,
            options={},
        )

        async def mock_fn(_job) -> None:
            return None

        await self.manager.run_job(job, mock_fn)
        assert job.status == JobStatus.SUCCESS
        assert job.finished_at is not None

    async def test_run_job_transitions_to_failed_on_error(self) -> None:
        job = self.manager.create_job(
            automation_type=AutomationType.TTS,
            config_path="/config.json",
            csv_path=None,
            options={},
        )

        async def failing_fn(_job) -> None:
            raise RuntimeError("test error")

        await self.manager.run_job(job, failing_fn)
        assert job.status == JobStatus.FAILED
        assert job.error is not None
        assert "test error" in job.error
