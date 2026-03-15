from __future__ import annotations

import sys
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.mark.asyncio
async def test_configs_list_contains_default() -> None:
    from server import app

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/configs")

    assert response.status_code == 200
    configs = response.json()
    assert isinstance(configs, list)
    assert "default" in configs


@pytest.mark.asyncio
async def test_config_load_default() -> None:
    from server import app

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/configs/default")

    assert response.status_code == 200
    data = response.json()
    assert "tts" in data or "live" in data


@pytest.mark.asyncio
async def test_config_missing_returns_404() -> None:
    from server import app

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/configs/nonexistent_client_xyz")

    assert response.status_code == 404
