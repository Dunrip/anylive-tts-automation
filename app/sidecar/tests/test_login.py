from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
pytest.importorskip(
    "shared", reason="shared module requires playwright which is not installed"
)


@pytest.mark.asyncio
async def test_login_success() -> None:
    from server import app

    session_data = {
        "setup_complete": True,
        "display_name": "Test User",
        "email": "test@example.com",
    }

    with TemporaryDirectory() as tmpdir:
        session_file = Path(tmpdir) / "state" / "session_state.json"
        session_file.parent.mkdir(parents=True, exist_ok=True)
        session_file.write_text(json.dumps(session_data))

        with patch("shared.setup_login", new_callable=AsyncMock) as mock_setup:
            with patch("server.get_app_data_dir", return_value=Path(tmpdir)):
                with patch("services.job_manager.job_manager") as mock_job_manager:
                    mock_job_manager.is_running = False
                    mock_setup.return_value = None

                    async with AsyncClient(
                        transport=ASGITransport(app=app), base_url="http://test"
                    ) as client:
                        response = await client.post("/api/session/login")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["display_name"] == "Test User"
    assert data["email"] == "test@example.com"


@pytest.mark.asyncio
async def test_login_error() -> None:
    from server import app

    with patch("shared.setup_login", new_callable=AsyncMock) as mock_setup:
        with patch("services.job_manager.job_manager") as mock_job_manager:
            mock_job_manager.is_running = False
            mock_setup.side_effect = RuntimeError("timeout")

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post("/api/session/login")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "error"
    assert "timeout" in data["error"]


@pytest.mark.asyncio
async def test_login_conflict_when_job_running() -> None:
    from server import app

    with patch("services.job_manager.job_manager") as mock_job_manager:
        mock_job_manager.is_running = True

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/api/session/login")

    assert response.status_code == 409
    data = response.json()
    assert "Cannot login while a job is running" in data["detail"]


@pytest.mark.asyncio
async def test_login_default_platform_tts() -> None:
    from server import app

    session_data = {
        "setup_complete": True,
        "display_name": "Test User",
        "email": "test@example.com",
    }

    with TemporaryDirectory() as tmpdir:
        session_file = Path(tmpdir) / "state" / "session_state.json"
        session_file.parent.mkdir(parents=True, exist_ok=True)
        session_file.write_text(json.dumps(session_data))

        with patch("shared.setup_login", new_callable=AsyncMock) as mock_setup:
            with patch("server.get_app_data_dir", return_value=Path(tmpdir)):
                with patch("services.job_manager.job_manager") as mock_job_manager:
                    mock_job_manager.is_running = False
                    mock_setup.return_value = None

                    async with AsyncClient(
                        transport=ASGITransport(app=app), base_url="http://test"
                    ) as client:
                        response = await client.post("/api/session/login")

        assert response.status_code == 200
        # Verify setup_login was called with TTS defaults
        mock_setup.assert_called_once()
        call_kwargs = mock_setup.call_args[1]
        assert call_kwargs["login_url"] == "https://app.anylive.jp"
        assert call_kwargs["session_filename"] == "state/session_state.json"
        assert call_kwargs["browser_data_subdir"] == "state/browser_data"
        assert call_kwargs["gui_mode"] is True


@pytest.mark.asyncio
async def test_login_platform_live() -> None:
    from server import app

    session_data = {
        "setup_complete": True,
        "display_name": "Test User",
        "email": "test@example.com",
    }

    with TemporaryDirectory() as tmpdir:
        session_file = Path(tmpdir) / "state" / "session_state_faq_default.json"
        session_file.parent.mkdir(parents=True, exist_ok=True)
        session_file.write_text(json.dumps(session_data))

        with patch("shared.setup_login", new_callable=AsyncMock) as mock_setup:
            with patch("server.get_app_data_dir", return_value=Path(tmpdir)):
                with patch("services.job_manager.job_manager") as mock_job_manager:
                    mock_job_manager.is_running = False
                    mock_setup.return_value = None

                    async with AsyncClient(
                        transport=ASGITransport(app=app), base_url="http://test"
                    ) as client:
                        response = await client.post(
                            "/api/session/login",
                            json={"platform": "live"},
                        )

        assert response.status_code == 200
        mock_setup.assert_called_once()
        call_kwargs = mock_setup.call_args[1]
        assert call_kwargs["login_url"] == "https://live.app.anylive.jp"
        assert call_kwargs["session_filename"] == "state/session_state_faq_default.json"
        assert call_kwargs["browser_data_subdir"] == "state/browser_data_faq_default"
        assert call_kwargs["gui_mode"] is True


@pytest.mark.asyncio
async def test_login_platform_live_uses_client_specific_session_paths() -> None:
    from server import app

    session_data = {
        "setup_complete": True,
        "display_name": "Brand User",
        "email": "brand@example.com",
    }

    with TemporaryDirectory() as tmpdir:
        session_file = Path(tmpdir) / "state" / "session_state_faq_brandA.json"
        session_file.parent.mkdir(parents=True, exist_ok=True)
        session_file.write_text(json.dumps(session_data))

        with patch("shared.setup_login", new_callable=AsyncMock) as mock_setup:
            with patch("server.get_app_data_dir", return_value=Path(tmpdir)):
                with patch("services.job_manager.job_manager") as mock_job_manager:
                    mock_job_manager.is_running = False
                    mock_setup.return_value = None

                    async with AsyncClient(
                        transport=ASGITransport(app=app), base_url="http://test"
                    ) as client:
                        response = await client.post(
                            "/api/session/login",
                            json={"platform": "live", "client": "brandA"},
                        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["display_name"] == "Brand User"
        assert data["email"] == "brand@example.com"
        mock_setup.assert_called_once()
        call_kwargs = mock_setup.call_args[1]
        assert call_kwargs["login_url"] == "https://live.app.anylive.jp"
        assert call_kwargs["session_filename"] == "state/session_state_faq_brandA.json"
        assert call_kwargs["browser_data_subdir"] == "state/browser_data_faq_brandA"
        assert call_kwargs["gui_mode"] is True


@pytest.mark.asyncio
async def test_login_backward_compat_no_body() -> None:
    from server import app

    session_data = {
        "setup_complete": True,
        "display_name": "Test User",
        "email": "test@example.com",
    }

    with TemporaryDirectory() as tmpdir:
        session_file = Path(tmpdir) / "state" / "session_state.json"
        session_file.parent.mkdir(parents=True, exist_ok=True)
        session_file.write_text(json.dumps(session_data))

        with patch("shared.setup_login", new_callable=AsyncMock) as mock_setup:
            with patch("server.get_app_data_dir", return_value=Path(tmpdir)):
                with patch("services.job_manager.job_manager") as mock_job_manager:
                    mock_job_manager.is_running = False
                    mock_setup.return_value = None

                    async with AsyncClient(
                        transport=ASGITransport(app=app), base_url="http://test"
                    ) as client:
                        # POST with no body should default to TTS
                        response = await client.post("/api/session/login")

        assert response.status_code == 200
        # Verify setup_login was called with TTS defaults (backward compat)
        mock_setup.assert_called_once()
        call_kwargs = mock_setup.call_args[1]
        assert call_kwargs["login_url"] == "https://app.anylive.jp"
        assert call_kwargs["session_filename"] == "state/session_state.json"
        assert call_kwargs["browser_data_subdir"] == "state/browser_data"
        assert call_kwargs["gui_mode"] is True
