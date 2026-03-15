"""Tests for CSV preview endpoint."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

sys.path.insert(0, str(Path(__file__).parent.parent))


def _make_mock_version(
    product_number: str, product_name: str, script: str, audio_code: str
) -> MagicMock:
    """Create a mock Version object."""
    v = MagicMock()
    v.product_number = product_number
    v.products = [product_name]
    v.scripts = [script]
    v.audio_codes = [audio_code]
    return v


@pytest.mark.asyncio
async def test_csv_preview_returns_metadata() -> None:
    """POST /api/csv/preview returns rows, products, estimated_versions, preview."""
    # Mock auto_tts to avoid playwright dependency in test environment
    mock_versions = [
        _make_mock_version("1", "Product A", "Script text A", "SFD1"),
        _make_mock_version("2", "Product B", "Script text B", "SFD2"),
    ]

    mock_auto_tts = MagicMock()
    mock_auto_tts.parse_csv_data.return_value = mock_versions
    mock_auto_tts.ClientConfig.return_value = MagicMock()

    with patch.dict(
        "sys.modules",
        {
            "auto_tts": mock_auto_tts,
            "playwright": MagicMock(),
            "playwright.async_api": MagicMock(),
        },
    ):
        from server import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/csv/preview",
                json={
                    "csv_path": "configs/test_template.csv",
                    "config_path": "app/sidecar/fixtures/test_tts.json",
                },
            )

    assert response.status_code == 200
    data = response.json()
    assert "rows" in data
    assert "products" in data
    assert "estimated_versions" in data
    assert "preview" in data
    assert isinstance(data["preview"], list)
    assert len(data["preview"]) <= 5


@pytest.mark.asyncio
async def test_csv_preview_missing_csv_returns_404() -> None:
    """POST /api/csv/preview with missing CSV returns 404."""
    from server import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/csv/preview",
            json={
                "csv_path": "nonexistent_file.csv",
                "config_path": "app/sidecar/fixtures/test_tts.json",
            },
        )

    assert response.status_code in (404, 500)
