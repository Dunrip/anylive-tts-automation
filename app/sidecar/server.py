from __future__ import annotations

import argparse
import asyncio
import contextlib
import socket
import sys
import threading
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes.config import router as config_router
from routes.csv_preview import router as csv_router
from routes.jobs import router as jobs_router
from routes.session import router as session_router

_SIDECAR_DIR = Path(__file__).resolve().parent
_APP_DIR = _SIDECAR_DIR.parent
_REPO_ROOT = _APP_DIR.parent

if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

_app_data_dir: Path = _REPO_ROOT


def get_app_data_dir() -> Path:
    return _app_data_dir


def get_configs_dir() -> Path:
    configs = _app_data_dir / "configs"
    if configs.exists():
        return configs
    return _REPO_ROOT / "configs"


app = FastAPI(title="AnyLive TTS Sidecar", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:1420", "tauri://localhost"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(config_router, prefix="/api")
app.include_router(session_router, prefix="/api")
app.include_router(csv_router, prefix="/api")
app.include_router(jobs_router, prefix="/api")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": "1.0.0"}


def _get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _stdin_watcher(shutdown_event: threading.Event) -> None:
    try:
        for line in sys.stdin:
            if line.strip() == "shutdown":
                shutdown_event.set()
                break
    except (EOFError, OSError):
        shutdown_event.set()


async def _wait_for_shutdown(
    shutdown_event: threading.Event, server: uvicorn.Server
) -> None:
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, shutdown_event.wait)
    server.should_exit = True


async def _run_server(port: int, shutdown_event: threading.Event) -> int:
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="error",
    )
    server = uvicorn.Server(config)
    monitor_task = asyncio.create_task(_wait_for_shutdown(shutdown_event, server))
    try:
        await server.serve()
        return 0
    finally:
        monitor_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await monitor_task


def main() -> None:
    global _app_data_dir

    parser = argparse.ArgumentParser(description="AnyLive TTS Sidecar Server")
    parser.add_argument(
        "--app-data-dir",
        type=Path,
        default=_REPO_ROOT,
        help="App data directory for configs and sessions",
    )
    args = parser.parse_args()
    _app_data_dir = args.app_data_dir

    port = _get_free_port()

    shutdown_event = threading.Event()
    stdin_thread = threading.Thread(
        target=_stdin_watcher,
        args=(shutdown_event,),
        daemon=True,
    )
    stdin_thread.start()

    print(f"SERVER_READY:{port}", flush=True)

    raise SystemExit(asyncio.run(_run_server(port, shutdown_event)))


if __name__ == "__main__":
    main()
