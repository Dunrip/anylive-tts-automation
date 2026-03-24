"""Tests for cross-platform Playwright path resolution."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch


from shared import get_playwright_cache_dir


class TestPlaywrightCacheDir:
    """Test cross-platform Playwright cache directory resolution."""

    def test_darwin_path(self) -> None:
        """Test macOS path resolution."""
        with patch("sys.platform", "darwin"):
            result = get_playwright_cache_dir()
            expected = Path.home() / "Library" / "Caches" / "ms-playwright"
            assert result == expected
            assert "Library" in str(result)
            assert "Caches" in str(result)

    def test_win32_path(self) -> None:
        """Test Windows path resolution."""
        localappdata = "C:\\Users\\TestUser\\AppData\\Local"
        with patch.dict(os.environ, {"LOCALAPPDATA": localappdata}):
            with patch("sys.platform", "win32"):
                result = get_playwright_cache_dir()
                assert "ms-playwright" in str(result)
                assert "AppData" in str(result) or "Local" in str(result)

    def test_win32_path_missing_localappdata(self) -> None:
        """Test Windows path resolution when LOCALAPPDATA is not set."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("LOCALAPPDATA", None)
            with patch("sys.platform", "win32"):
                result = get_playwright_cache_dir()
                assert "ms-playwright" in str(result)

    def test_linux_path(self) -> None:
        """Test Linux path resolution."""
        with patch("sys.platform", "linux"):
            result = get_playwright_cache_dir()
            expected = Path.home() / ".cache" / "ms-playwright"
            assert result == expected
            assert ".cache" in str(result)

    def test_unix_path(self) -> None:
        """Test generic Unix path resolution."""
        with patch("sys.platform", "freebsd"):
            result = get_playwright_cache_dir()
            expected = Path.home() / ".cache" / "ms-playwright"
            assert result == expected

    def test_returns_path_object(self) -> None:
        """Test that the function returns a Path object."""
        result = get_playwright_cache_dir()
        assert isinstance(result, Path)

    def test_path_contains_ms_playwright(self) -> None:
        """Test that all paths contain 'ms-playwright'."""
        result = get_playwright_cache_dir()
        assert "ms-playwright" in str(result)
