from __future__ import annotations

import asyncio

from models.job import AutomationType, JobStatus
from services.job_manager import JobManager, make_job_done_callback


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

    async def test_cancelled_status_preserved_after_completion(self) -> None:
        """Test that CANCELLED status is not overwritten to SUCCESS when coroutine finishes."""
        import asyncio

        job = self.manager.create_job(
            automation_type=AutomationType.TTS,
            config_path="/config.json",
            csv_path=None,
            options={},
        )

        # Use an Event to control timing: allow us to set CANCELLED mid-execution
        cancel_event = asyncio.Event()

        async def mock_fn_with_timing(_job) -> None:
            # Signal that we're running
            cancel_event.set()
            # Simulate some work
            await asyncio.sleep(0.05)

        # Start the automation
        task = asyncio.create_task(self.manager.run_job(job, mock_fn_with_timing))

        # Wait for the function to start
        await cancel_event.wait()

        # Set status to CANCELLED while the coroutine is still running
        job.status = JobStatus.CANCELLED

        # Wait for the coroutine to finish
        await task

        # Assert that CANCELLED was preserved, not overwritten to SUCCESS
        assert job.status == JobStatus.CANCELLED
        assert job.finished_at is not None

    async def test_success_set_when_not_cancelled(self) -> None:
        """Test that normal completion still sets SUCCESS status."""
        job = self.manager.create_job(
            automation_type=AutomationType.TTS,
            config_path="/config.json",
            csv_path=None,
            options={},
        )

        async def mock_fn(_job) -> None:
            await asyncio.sleep(0.01)

        await self.manager.run_job(job, mock_fn)
        assert (
            job.status == JobStatus.SUCCESS
        ), f"Expected SUCCESS but got {job.status}, error: {job.error}"
        assert job.finished_at is not None

    async def test_done_callback_captures_exception_and_marks_job_failed(self) -> None:
        job = self.manager.create_job(
            automation_type=AutomationType.TTS,
            config_path="/config.json",
            csv_path=None,
            options={},
        )
        job.status = JobStatus.RUNNING

        async def raising_fn() -> None:
            raise RuntimeError("fire-and-forget exception")

        task = asyncio.create_task(raising_fn())
        task.add_done_callback(make_job_done_callback(job))

        try:
            await task
        except RuntimeError:
            pass

        assert job.status == JobStatus.FAILED
        assert job.error is not None
        assert "fire-and-forget exception" in job.error
        assert job.finished_at is not None
