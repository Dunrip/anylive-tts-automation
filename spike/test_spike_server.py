# pyright: reportMissingImports=false
from __future__ import annotations

import select
import subprocess
import time
from pathlib import Path

import httpx


def _start_server() -> tuple[subprocess.Popen[str], int]:
    spike_dir = Path(__file__).resolve().parent
    proc = subprocess.Popen(
        ["python3", "spike_server.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.PIPE,
        text=True,
        cwd=spike_dir,
    )
    assert proc.stdout is not None

    line = ""
    for _ in range(50):
        ready, _, _ = select.select([proc.stdout], [], [], 0.1)
        if ready:
            line = proc.stdout.readline().strip()
            if "SERVER_READY:" in line:
                break

    assert "SERVER_READY:" in line
    port = int(line.split(":")[1])
    return proc, port


def _shutdown(proc: subprocess.Popen[str]) -> None:
    assert proc.stdin is not None
    proc.stdin.write("shutdown\n")
    proc.stdin.flush()
    proc.wait(timeout=5)


def test_health_endpoint() -> None:
    proc, port = _start_server()
    try:
        response = None
        for _ in range(30):
            try:
                response = httpx.get(f"http://127.0.0.1:{port}/health", timeout=1.0)
                break
            except httpx.ConnectError:
                time.sleep(0.1)

        assert response is not None
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
    finally:
        _shutdown(proc)
        assert proc.returncode == 0


def test_stdin_shutdown() -> None:
    proc, _ = _start_server()
    _shutdown(proc)
    assert proc.returncode == 0
