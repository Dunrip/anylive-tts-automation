from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.mark.asyncio
async def test_session_endpoint_returns_valid_true_when_setup_complete() -> None:
    from server import app
    from unittest.mock import patch

    session_data = {
        "setup_complete": True,
        "timestamp": "2025-03-17T12:00:00",
        "email": "user@example.com",
        "display_name": "Test User",
    }

    with TemporaryDirectory() as tmpdir:
        session_file = Path(tmpdir) / "session_state.json"
        session_file.write_text(json.dumps(session_data))

        with patch("routes.session._get_session_file", return_value=session_file):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/api/session/test_client/test_site")

    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert data["client"] == "test_client"
    assert data["site"] == "test_site"
    assert data["email"] == "user@example.com"
    assert data["display_name"] == "Test User"
    assert "checked_at" in data


@pytest.mark.asyncio
async def test_session_endpoint_returns_valid_false_when_setup_incomplete() -> None:
    from server import app
    from unittest.mock import patch

    session_data = {
        "setup_complete": False,
        "timestamp": "2025-03-17T12:00:00",
    }

    with TemporaryDirectory() as tmpdir:
        session_file = Path(tmpdir) / "session_state.json"
        session_file.write_text(json.dumps(session_data))

        with patch("routes.session._get_session_file", return_value=session_file):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/api/session/test_client/test_site")

    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is False
    assert data["email"] is None
    assert data["display_name"] is None


@pytest.mark.asyncio
async def test_session_endpoint_returns_valid_false_when_file_missing() -> None:
    from server import app
    from unittest.mock import patch

    with patch(
        "routes.session._get_session_file",
        return_value=Path("/nonexistent/session_state.json"),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/session/test_client/test_site")

    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is False
    assert data["email"] is None
    assert data["display_name"] is None


@pytest.mark.asyncio
async def test_session_endpoint_returns_valid_false_when_file_malformed() -> None:
    from server import app
    from unittest.mock import patch

    with TemporaryDirectory() as tmpdir:
        session_file = Path(tmpdir) / "session_state.json"
        session_file.write_text("invalid json {")

        with patch("routes.session._get_session_file", return_value=session_file):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/api/session/test_client/test_site")

    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is False
    assert data["email"] is None
    assert data["display_name"] is None


@pytest.mark.asyncio
async def test_session_endpoint_handles_missing_email_field() -> None:
    from server import app
    from unittest.mock import patch

    session_data = {
        "setup_complete": True,
        "timestamp": "2025-03-17T12:00:00",
    }

    with TemporaryDirectory() as tmpdir:
        session_file = Path(tmpdir) / "session_state.json"
        session_file.write_text(json.dumps(session_data))

        with patch("routes.session._get_session_file", return_value=session_file):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/api/session/test_client/test_site")

    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert data["email"] is None
    assert data["display_name"] is None
