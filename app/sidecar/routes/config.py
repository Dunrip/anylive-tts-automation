from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter()


def _strip_jsonc_comments(text: str) -> str:
    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("//"):
            continue

        idx = line.find("//")
        while idx != -1:
            prefix = line[:idx]
            if prefix.count('"') % 2 == 0:
                line = prefix.rstrip()
                break
            idx = line.find("//", idx + 2)
        lines.append(line)
    return "\n".join(lines)


def _load_jsonc(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    return json.loads(_strip_jsonc_comments(text))


def _get_configs_dir() -> Path:
    from server import get_configs_dir

    return get_configs_dir()


@router.get("/configs")
async def list_configs() -> list[str]:
    configs_dir = _get_configs_dir()
    if not configs_dir.exists():
        return []

    return [
        entry.name
        for entry in sorted(configs_dir.iterdir())
        if entry.is_dir() and not entry.name.startswith(".")
    ]


@router.get("/configs/{client}")
async def get_config(client: str) -> dict[str, Any]:
    configs_dir = _get_configs_dir()
    client_dir = configs_dir / client
    if not client_dir.exists():
        raise HTTPException(status_code=404, detail=f"Config '{client}' not found")

    result: dict[str, Any] = {"client": client}
    tts_path = client_dir / "tts.json"
    if tts_path.exists():
        result["tts"] = _load_jsonc(tts_path)

    live_path = client_dir / "live.json"
    if live_path.exists():
        result["live"] = _load_jsonc(live_path)

    return result


@router.put("/configs/{client}")
async def update_config(client: str, body: dict[str, Any]) -> dict[str, str]:
    configs_dir = _get_configs_dir()
    client_dir = configs_dir / client
    if not client_dir.exists():
        raise HTTPException(status_code=404, detail=f"Config '{client}' not found")

    if "tts" in body:
        tts_path = client_dir / "tts.json"
        tts_path.write_text(
            json.dumps(body["tts"], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    if "live" in body:
        live_path = client_dir / "live.json"
        live_path.write_text(
            json.dumps(body["live"], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    return {"status": "saved"}


@router.post("/configs")
async def create_config(body: dict[str, Any]) -> dict[str, str]:
    """Create a new client config by copying from default."""
    import shutil

    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="Client name is required")

    if not all(c.isalnum() or c in "-_" for c in name):
        raise HTTPException(status_code=422, detail="Name must be alphanumeric, hyphens, or underscores only")

    configs_dir = _get_configs_dir()
    client_dir = configs_dir / name
    if client_dir.exists():
        raise HTTPException(status_code=409, detail=f"Config '{name}' already exists")

    default_dir = configs_dir / "default"
    if default_dir.exists():
        shutil.copytree(default_dir, client_dir)
    else:
        client_dir.mkdir(parents=True)
        (client_dir / "tts.json").write_text("{}", encoding="utf-8")
        (client_dir / "live.json").write_text("{}", encoding="utf-8")

    return {"status": "created", "client": name}
