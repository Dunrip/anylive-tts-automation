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
    assert len(data["preview"]) == 2
    assert "capped" in data
    assert data["capped"] is False


@pytest.mark.asyncio
async def test_csv_preview_returns_all_rows_with_cap() -> None:
    """POST /api/csv/preview returns all rows from all versions without capping."""
    # Create mock with 3 versions having 10 scripts each (30 total rows)
    mock_versions = [
        _make_mock_version("1", "Product A", "Script A", "SFD1"),
        _make_mock_version("2", "Product B", "Script B", "SFD2"),
        _make_mock_version("3", "Product C", "Script C", "SFD3"),
    ]
    # Add multiple scripts to each version
    for v in mock_versions:
        v.scripts = [f"Script {i}" for i in range(10)]
        v.audio_codes = [f"SFD{i}" for i in range(10)]

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
    assert len(data["preview"]) == 30
    assert data["capped"] is False


@pytest.mark.asyncio
async def test_csv_preview_caps_at_max_rows() -> None:
    """POST /api/csv/preview caps preview at 200 rows and sets capped flag."""
    # Create mock with enough versions/scripts to exceed 200 rows
    # 25 versions × 10 scripts each = 250 rows
    mock_versions = []
    for v_num in range(25):
        v = MagicMock()
        v.product_number = str(v_num + 1)
        v.products = [f"Product {v_num + 1}"]
        v.scripts = [f"Script {i}" for i in range(10)]
        v.audio_codes = [f"SFD{i}" for i in range(10)]
        mock_versions.append(v)

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
    assert len(data["preview"]) == 200
    assert data["capped"] is True


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


@pytest.mark.asyncio
async def test_csv_preview_faq_type_returns_200() -> None:
    """POST /api/csv/preview with automation_type=faq returns 200 with expected keys."""
    mock_product = MagicMock()
    mock_product.product_number = 1
    mock_product.product_name = "Product A"
    mock_row = MagicMock()
    mock_row.question = "Question text"
    mock_row.audio_code = "SFD1"
    mock_product.rows = [mock_row]

    mock_auto_faq = MagicMock()
    mock_auto_faq.parse_faq_csv.return_value = [mock_product]
    mock_auto_faq.FAQConfig.return_value = MagicMock()

    with patch.dict(
        "sys.modules",
        {
            "auto_tts": MagicMock(),
            "auto_faq": mock_auto_faq,
            "auto_script": MagicMock(),
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
                    "automation_type": "faq",
                },
            )

    assert response.status_code == 200
    data = response.json()
    assert "rows" in data
    assert "products" in data
    assert "estimated_versions" in data
    assert "preview" in data
    assert "capped" in data
    assert isinstance(data["preview"], list)


@pytest.mark.asyncio
async def test_csv_preview_script_type_returns_200() -> None:
    """POST /api/csv/preview with automation_type=script returns 200 with expected keys."""
    mock_product = MagicMock()
    mock_product.product_number = 1
    mock_product.product_name = "Product A"
    mock_row = MagicMock()
    mock_row.script_content = "Script text"
    mock_row.audio_code = "SFD1"
    mock_product.rows = [mock_row]

    mock_auto_script = MagicMock()
    mock_auto_script.parse_script_csv.return_value = [mock_product]
    mock_auto_script.ScriptConfig.return_value = MagicMock()

    with patch.dict(
        "sys.modules",
        {
            "auto_tts": MagicMock(),
            "auto_faq": MagicMock(),
            "auto_script": mock_auto_script,
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
                    "automation_type": "script",
                },
            )

    assert response.status_code == 200
    data = response.json()
    assert "rows" in data
    assert "products" in data
    assert "estimated_versions" in data
    assert "preview" in data
    assert "capped" in data
    assert isinstance(data["preview"], list)


@pytest.mark.asyncio
async def test_csv_preview_tts_default_still_works() -> None:
    """POST /api/csv/preview without automation_type defaults to tts and returns 200."""
    mock_versions = [
        _make_mock_version("1", "Product A", "Script text A", "SFD1"),
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
                    # automation_type omitted - should default to "tts"
                },
            )

    assert response.status_code == 200
    data = response.json()
    assert "rows" in data
    assert "products" in data
    assert "estimated_versions" in data
    assert "preview" in data
    assert "capped" in data


@pytest.mark.asyncio
async def test_csv_preview_invalid_type_returns_422() -> None:
    """POST /api/csv/preview with invalid automation_type returns 422."""
    from server import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/csv/preview",
            json={
                "csv_path": "configs/test_template.csv",
                "config_path": "app/sidecar/fixtures/test_tts.json",
                "automation_type": "invalid_type",
            },
        )

    assert response.status_code == 422
