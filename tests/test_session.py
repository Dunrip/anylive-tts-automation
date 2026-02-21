import json
from datetime import datetime

from auto_tts import is_session_valid


class TestIsSessionValid:
    def test_file_exists_with_valid_content(self, tmp_path, monkeypatch):
        session_file = tmp_path / "session_state.json"
        session_file.write_text(json.dumps({"setup_complete": True, "timestamp": datetime.now().isoformat()}))
        monkeypatch.setattr("auto_tts.get_session_file_path", lambda: str(session_file))
        assert is_session_valid() is True

    def test_file_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr("auto_tts.get_session_file_path", lambda: str(tmp_path / "nonexistent.json"))
        assert is_session_valid() is False

    def test_file_exists_but_setup_not_complete(self, tmp_path, monkeypatch):
        session_file = tmp_path / "session_state.json"
        session_file.write_text(json.dumps({"setup_complete": False, "timestamp": datetime.now().isoformat()}))
        monkeypatch.setattr("auto_tts.get_session_file_path", lambda: str(session_file))
        assert is_session_valid() is False

    def test_file_exists_but_invalid_json(self, tmp_path, monkeypatch):
        session_file = tmp_path / "session_state.json"
        session_file.write_text("not json")
        monkeypatch.setattr("auto_tts.get_session_file_path", lambda: str(session_file))
        assert is_session_valid() is False

    def test_stale_session_still_valid(self, tmp_path, monkeypatch):
        """A session older than 30 days is still valid (just triggers a warning)."""
        session_file = tmp_path / "session_state.json"
        session_file.write_text(json.dumps({"setup_complete": True, "timestamp": "2025-01-01T00:00:00"}))
        monkeypatch.setattr("auto_tts.get_session_file_path", lambda: str(session_file))
        assert is_session_valid() is True
