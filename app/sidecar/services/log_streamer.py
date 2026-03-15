from __future__ import annotations

import asyncio
import json
from typing import Any, Callable

from fastapi import WebSocket


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
            except Exception:
                dead.append(websocket)

        for websocket in dead:
            self.disconnect(job_id, websocket)

    def make_log_callback(self, job_id: str) -> Callable[[dict[str, Any]], None]:
        def callback(message: dict[str, Any]) -> None:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self.broadcast(job_id, message))
            except RuntimeError:
                pass

        return callback


log_streamer = LogStreamer()
