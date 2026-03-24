from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from httpx import AsyncClient, ASGITransport

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestHistoryStore:
    def test_get_runs_returns_empty_when_no_db(self) -> None:
        from services.history_store import get_runs

        runs = get_runs()
        assert isinstance(runs, list)

    def test_save_run_returns_id(self) -> None:
        from services.history_store import save_run
        from models.job import JobStatus, AutomationType, JobProgress

        mock_job = MagicMock()
        mock_job.job_id = "test-job-123"
        mock_job.automation_type = AutomationType.TTS
        mock_job.status = JobStatus.SUCCESS
        mock_job.started_at = "2026-01-01T00:00:00Z"
        mock_job.finished_at = "2026-01-01T00:01:00Z"
        mock_job.progress = JobProgress(current=5, total=5)
        mock_job.error = None
        mock_job.csv_path = "/path/to/data.csv"

        run_id = save_run(mock_job)
        assert isinstance(run_id, str)
        assert len(run_id) > 0


@pytest.mark.asyncio
async def test_history_endpoint_returns_empty_list() -> None:
    from server import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/history")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_history_run_not_found_returns_404() -> None:
    from server import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/history/nonexistent-run-id")

    assert response.status_code == 404
