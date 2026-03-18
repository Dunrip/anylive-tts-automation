from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(autouse=True)
def reset_global_job_manager() -> None:
    from services.job_manager import job_manager

    job_manager._current_job = None
    job_manager._jobs = {}


async def test_start_job_returns_202() -> None:
    from server import app

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/jobs",
            json={
                "automation_type": "tts",
                "config_path": "app/sidecar/fixtures/test_tts.json",
                "csv_path": "configs/test_template.csv",
                "options": {"headless": True, "dry_run": True},
            },
        )

    assert response.status_code == 202
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "accepted"


async def test_get_job_status() -> None:
    from models.job import AutomationType
    from server import app
    from services.job_manager import job_manager

    job = job_manager.create_job(
        automation_type=AutomationType.TTS,
        config_path="test.json",
        csv_path=None,
        options={},
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(f"/api/jobs/{job.job_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == job.job_id
    assert "status" in data


async def test_get_nonexistent_job_returns_404() -> None:
    from server import app

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/jobs/nonexistent-job-id")

    assert response.status_code == 404


async def test_start_job_while_running_returns_409() -> None:
    from models.job import AutomationType, JobStatus
    from server import app
    from services.job_manager import job_manager

    running = job_manager.create_job(
        automation_type=AutomationType.TTS,
        config_path="test.json",
        csv_path=None,
        options={},
    )
    running.status = JobStatus.RUNNING

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/jobs",
            json={
                "automation_type": "tts",
                "config_path": "app/sidecar/fixtures/test_tts.json",
                "csv_path": "configs/test_template.csv",
                "options": {"headless": True, "dry_run": True},
            },
        )

    assert response.status_code == 409


def test_websocket_stream_emits_log_messages() -> None:
    from server import app

    with TestClient(app) as client:
        with client.websocket_connect("/api/jobs/temp-job/ws") as websocket:
            from services.log_streamer import log_streamer

            payload = {
                "type": "log",
                "level": "INFO",
                "message": "hello",
                "timestamp": "2026-01-01T00:00:00+00:00",
                "version": None,
            }

            client.portal.call(log_streamer.broadcast, "temp-job", payload)

            received = websocket.receive_text()
            assert json.loads(received) == payload


@pytest.mark.asyncio
async def test_cancel_job() -> None:
    from models.job import JobStatus
    from server import app

    mock_job = MagicMock()
    mock_job.job_id = "cancel-test-job"
    mock_job.status = JobStatus.RUNNING
    mock_job.finished_at = None
    mock_job.emit_log = MagicMock()
    mock_job.emit_status = MagicMock()

    with patch("routes.jobs.job_manager") as mock_jm:
        mock_jm.get_job.return_value = mock_job
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/api/jobs/cancel-test-job/cancel")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "cancelled"
