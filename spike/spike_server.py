# pyright: reportMissingImports=false
from __future__ import annotations

import asyncio
import contextlib
import socket
import sys
import threading

from fastapi import FastAPI
import uvicorn

app = FastAPI()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


def stdin_watcher(shutdown_event: threading.Event) -> None:
    for line in sys.stdin:
        if line.strip() == "shutdown":
            shutdown_event.set()
            break


def _get_free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return int(port)


async def _wait_for_shutdown(
    shutdown_event: threading.Event, server: uvicorn.Server
) -> None:
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, shutdown_event.wait)
    server.should_exit = True


async def _run_server(port: int, shutdown_event: threading.Event) -> int:
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    monitor_task = asyncio.create_task(_wait_for_shutdown(shutdown_event, server))
    try:
        await server.serve()
        return 0
    finally:
        monitor_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await monitor_task


if __name__ == "__main__":
    port = _get_free_port()
    shutdown_event = threading.Event()
    stdin_thread = threading.Thread(
        target=stdin_watcher, args=(shutdown_event,), daemon=True
    )
    stdin_thread.start()
    print(f"SERVER_READY:{port}", flush=True)
    raise SystemExit(asyncio.run(_run_server(port, shutdown_event)))
