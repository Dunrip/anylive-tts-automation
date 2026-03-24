"""Configuration models for AnyLive TTS automation."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class CSVColumns(BaseModel):
    product_number: str = "No."
    product_name: str = "Product Name"
    script_content: str = "TH Script"
    audio_code: str = "Audio Code"


class TTSConfig(BaseModel):
    base_url: str
    version_template: str
    voice_name: str
    max_scripts_per_version: int = 10
    enable_voice_selection: bool = False
    enable_product_info: bool = False
    csv_columns: CSVColumns = CSVColumns()


class LiveConfig(BaseModel):
    audio_dir: Optional[str] = None
    audio_extensions: list[str] = [".mp3", ".wav"]
    csv_columns: Optional[CSVColumns] = None


class SessionStatus(BaseModel):
    valid: bool
    site: str
    client: str
    checked_at: str
