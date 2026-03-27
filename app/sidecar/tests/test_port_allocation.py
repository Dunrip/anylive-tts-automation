from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_get_free_port_returns_valid_ports() -> None:
    from server import _get_free_port

    ports = [_get_free_port() for _ in range(10)]

    for port in ports:
        assert 1 <= port <= 65535, f"Port {port} is out of valid range (1-65535)"
