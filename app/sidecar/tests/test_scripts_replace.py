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


async def test_scripts_replace_returns_202() -> None:
    from server import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/scripts/replace",
            json={
                "config_path": "app/sidecar/fixtures/test_live.json",
                "options": {"headless": True, "dry_run": True},
            },
        )

    assert response.status_code == 202
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "accepted"


async def test_scripts_replace_while_running_returns_409() -> None:
    from models.job import AutomationType, JobStatus
    from server import app
    from services.job_manager import job_manager

    running = job_manager.create_job(
        automation_type=AutomationType.SCRIPT,
        config_path="test.json",
        csv_path=None,
        options={"replace_products": True},
    )
    running.status = JobStatus.RUNNING

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/scripts/replace",
            json={
                "config_path": "app/sidecar/fixtures/test_live.json",
                "options": {},
            },
        )

    assert response.status_code == 409

    running.status = JobStatus.SUCCESS
    job_manager._current_job = None


async def test_scripts_replace_injects_replace_products_true() -> None:
    from server import app
    from services.job_manager import job_manager

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/scripts/replace",
            json={
                "config_path": "app/sidecar/fixtures/test_live.json",
                "options": {"headless": True},
            },
        )

    assert response.status_code == 202
    job_id = response.json()["job_id"]
    job = job_manager.get_job(job_id)
    assert job is not None
    assert job.options.get("replace_products") is True
