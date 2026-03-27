from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable

from fastapi import WebSocket

_logger = logging.getLogger(__name__)


def _log_broadcast_exception(task: asyncio.Task) -> None:
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        _logger.error("Unhandled exception in broadcast task: %s", exc, exc_info=exc)


class LogStreamer:
    def __init__(self) -> None:
        self._connections: dict[str, list[WebSocket]] = {}

    async def connect(self, job_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.setdefault(job_id, []).append(websocket)

    def disconnect(self, job_id: str, websocket: WebSocket) -> None:
        if job_id not in self._connections:
            return
        try:
            self._connections[job_id].remove(websocket)
        except ValueError:
            pass
        if not self._connections[job_id]:
            _logger.warning(
                "All WebSocket clients disconnected for job %s, job still running",
                job_id,
            )
            del self._connections[job_id]

    async def broadcast(self, job_id: str, message: dict[str, Any]) -> None:
        sockets = self._connections.get(job_id)
        if not sockets:
            return

        dead: list[WebSocket] = []
        payload = json.dumps(message)
        for websocket in list(sockets):
            try:
                await websocket.send_text(payload)
            except Exception as exc:
                _logger.warning(
                    "WebSocket send failed for job %s: %s: %s",
                    job_id,
                    type(exc).__name__,
                    exc,
                )
                dead.append(websocket)

        for websocket in dead:
            self.disconnect(job_id, websocket)

    def cleanup_job(self, job_id: str) -> None:
        self._connections.pop(job_id, None)

    def make_log_callback(self, job_id: str) -> Callable[[dict[str, Any]], None]:
        def callback(message: dict[str, Any]) -> None:
            try:
                loop = asyncio.get_running_loop()
                t = loop.create_task(self.broadcast(job_id, message))
                t.add_done_callback(_log_broadcast_exception)
            except RuntimeError:
                _logger.debug("No event loop for log broadcast (job %s)", job_id)

        return callback


log_streamer = LogStreamer()
