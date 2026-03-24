"""Tests for cross-platform keyboard modifier constant."""

import importlib
import sys
from unittest.mock import patch


class TestModifierKey:
    """Test MODIFIER_KEY constant for platform-aware keyboard shortcuts."""

    def test_modifier_is_meta_on_darwin(self) -> None:
        """MODIFIER_KEY should be 'Meta' on macOS (darwin)."""
        with patch.object(sys, "platform", "darwin"):
            import shared

            importlib.reload(shared)
            assert shared.MODIFIER_KEY == "Meta"

    def test_modifier_is_control_on_windows(self) -> None:
        """MODIFIER_KEY should be 'Control' on Windows."""
        with patch.object(sys, "platform", "win32"):
            import shared

            importlib.reload(shared)
            assert shared.MODIFIER_KEY == "Control"

    def test_modifier_is_control_on_linux(self) -> None:
        """MODIFIER_KEY should be 'Control' on Linux."""
        with patch.object(sys, "platform", "linux"):
            import shared

            importlib.reload(shared)
            assert shared.MODIFIER_KEY == "Control"

    def test_modifier_key_imported_in_auto_tts(self) -> None:
        """MODIFIER_KEY should be importable from auto_tts.py."""
        import auto_tts

        assert hasattr(auto_tts, "MODIFIER_KEY")
        assert auto_tts.MODIFIER_KEY in ("Meta", "Control")
