"""Tests for setup endpoints."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from httpx import AsyncClient, ASGITransport

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.mark.asyncio
async def test_chromium_status_returns_installed_field() -> None:
    from server import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/setup/chromium-status")

    assert response.status_code == 200
    data = response.json()
    assert "installed" in data
    assert isinstance(data["installed"], bool)
    assert "path" in data


@pytest.mark.asyncio
async def test_install_chromium_when_already_installed() -> None:
    from server import app
    from unittest.mock import patch

    with patch("routes.setup._get_chromium_path", return_value=Path("/fake/chromium")):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/api/setup/install-chromium")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "already_installed"
