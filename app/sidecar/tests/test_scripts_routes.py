from __future__ import annotations

import sys
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(autouse=True)
def reset_job_manager() -> None:
    from services.job_manager import job_manager

    job_manager._current_job = None
    job_manager._jobs = {}


async def test_scripts_run_returns_202() -> None:
    from server import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/scripts/run",
            json={
                "config_path": "app/sidecar/fixtures/test_live.json",
                "csv_path": "configs/test_template.csv",
                "options": {"headless": True, "dry_run": True},
            },
        )

    assert response.status_code == 202
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "accepted"


async def test_scripts_delete_returns_202_without_csv() -> None:
    from server import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/scripts/delete",
            json={
                "config_path": "app/sidecar/fixtures/test_live.json",
                "options": {"headless": True, "dry_run": True},
            },
        )

    assert response.status_code == 202
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "accepted"


async def test_scripts_run_while_running_returns_409() -> None:
    from models.job import AutomationType, JobStatus
    from server import app
    from services.job_manager import job_manager

    running = job_manager.create_job(
        automation_type=AutomationType.SCRIPT,
        config_path="test.json",
        csv_path="test.csv",
        options={},
    )
    running.status = JobStatus.RUNNING

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/scripts/run",
            json={
                "config_path": "app/sidecar/fixtures/test_live.json",
                "csv_path": "configs/test_template.csv",
                "options": {},
            },
        )

    assert response.status_code == 409

    running.status = JobStatus.SUCCESS
    job_manager._current_job = None


async def test_scripts_delete_while_running_returns_409() -> None:
    from models.job import AutomationType, JobStatus
    from server import app
    from services.job_manager import job_manager

    running = job_manager.create_job(
        automation_type=AutomationType.SCRIPT,
        config_path="test.json",
        csv_path=None,
        options={"delete_scripts": True},
    )
    running.status = JobStatus.RUNNING

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/scripts/delete",
            json={
                "config_path": "app/sidecar/fixtures/test_live.json",
                "options": {},
            },
        )

    assert response.status_code == 409

    running.status = JobStatus.SUCCESS
    job_manager._current_job = None


async def test_run_script_job_passes_cancel_check_callback(monkeypatch) -> None:
    from models.job import AutomationType, JobStatus
    from routes import scripts as scripts_route
    from services.job_manager import job_manager

    captured: dict[str, object] = {}

    async def fake_run_job(**kwargs):
        captured.update(kwargs)
        return {"success": True}

    monkeypatch.setattr("auto_script.run_job", fake_run_job)

    job = job_manager.create_job(
        automation_type=AutomationType.SCRIPT,
        config_path="app/sidecar/fixtures/test_live.json",
        csv_path="configs/test_template.csv",
        options={},
    )
    job.status = JobStatus.RUNNING

    await scripts_route._run_script_job(job)

    cancel_check = captured.get("cancel_check")
    assert callable(cancel_check)
    assert cancel_check() is False
    job.status = JobStatus.CANCELLED
    assert cancel_check() is True
