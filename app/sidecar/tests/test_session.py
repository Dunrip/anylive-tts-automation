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


def test_get_session_file_returns_client_specific_live_path() -> None:
    from routes.session import _get_session_file
    from unittest.mock import patch

    with TemporaryDirectory() as tmpdir:
        with patch("server.get_app_data_dir", return_value=Path(tmpdir)):
            brand_a = _get_session_file("brandA", "live")
            brand_b = _get_session_file("brandB", "faq")
            tts = _get_session_file("ignored", "tts")

    assert brand_a == Path(tmpdir) / "state" / "session_state_faq_brandA.json"
    assert brand_b == Path(tmpdir) / "state" / "session_state_faq_brandB.json"
    assert brand_a != brand_b
    assert tts == Path(tmpdir) / "state" / "session_state.json"


@pytest.mark.asyncio
async def test_session_endpoint_returns_different_client_states_for_live() -> None:
    from server import app
    from unittest.mock import patch

    brand_a_data = {
        "setup_complete": True,
        "email": "brand-a@example.com",
        "display_name": "Brand A",
    }
    brand_b_data = {
        "setup_complete": True,
        "email": "brand-b@example.com",
        "display_name": "Brand B",
    }

    with TemporaryDirectory() as tmpdir:
        state_dir = Path(tmpdir) / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        (state_dir / "session_state_faq_brandA.json").write_text(
            json.dumps(brand_a_data)
        )
        (state_dir / "session_state_faq_brandB.json").write_text(
            json.dumps(brand_b_data)
        )

        with patch("server.get_app_data_dir", return_value=Path(tmpdir)):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response_a = await client.get("/api/session/brandA/live")
                response_b = await client.get("/api/session/brandB/live")

    assert response_a.status_code == 200
    assert response_b.status_code == 200
    data_a = response_a.json()
    data_b = response_b.json()
    assert data_a["valid"] is True
    assert data_b["valid"] is True
    assert data_a["email"] == "brand-a@example.com"
    assert data_b["email"] == "brand-b@example.com"
    assert data_a["display_name"] == "Brand A"
    assert data_b["display_name"] == "Brand B"
    assert data_a != data_b
