"""WebSocket message schemas for real-time job streaming."""

from __future__ import annotations

from enum import Enum
from typing import Literal, Optional, Union

from pydantic import BaseModel


class LogLevel(str, Enum):
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"
    DEBUG = "DEBUG"


class LogMessage(BaseModel):
    type: Literal["log"] = "log"
    level: LogLevel
    message: str
    timestamp: str
    version: Optional[str] = None


class ProgressMessage(BaseModel):
    type: Literal["progress"] = "progress"
    current: int
    total: int
    version_name: str


class StatusMessage(BaseModel):
    type: Literal["status"] = "status"
    job_id: str
    status: str


WSMessage = Union[LogMessage, ProgressMessage, StatusMessage]
