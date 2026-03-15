from __future__ import annotations

import logging
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

_logger = logging.getLogger(__name__)


class CSVPreviewRequest(BaseModel):
    csv_path: str
    config_path: str


@router.post("/csv/preview")
async def preview_csv(request: CSVPreviewRequest) -> dict:
    try:
        from auto_tts import ClientConfig, parse_csv_data
        from shared import load_csv, load_jsonc

        config_path = Path(request.config_path)
        if not config_path.is_absolute():
            config_path = _REPO_ROOT / config_path
        if not config_path.exists():
            raise HTTPException(
                status_code=404, detail=f"Config not found: {request.config_path}"
            )

        config_data = load_jsonc(str(config_path))
        config = ClientConfig(**config_data)

        csv_path = Path(request.csv_path)
        if not csv_path.is_absolute():
            csv_path = _REPO_ROOT / csv_path
        if not csv_path.exists():
            raise HTTPException(
                status_code=404, detail=f"CSV not found: {request.csv_path}"
            )

        df = load_csv(str(csv_path), _logger)
        versions = parse_csv_data(df, config, _logger)

        preview_rows: list[dict[str, str]] = []
        for version in versions[:5]:
            if not version.scripts:
                continue
            preview_rows.append(
                {
                    "no": version.product_number,
                    "product_name": version.products[0] if version.products else "",
                    "script": version.scripts[0][:100] if version.scripts else "",
                    "audio_code": version.audio_codes[0] if version.audio_codes else "",
                }
            )

        return {
            "rows": sum(len(version.scripts) for version in versions),
            "products": len({version.product_number for version in versions}),
            "estimated_versions": len(versions),
            "preview": preview_rows,
            "errors": [],
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
