from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

_logger = logging.getLogger(__name__)


# patch.dict("sys.modules", ...) restores sys.modules to its pre-context
# snapshot on exit, removing every C-extension library imported inside the
# context (numpy raises "cannot load module more than once per process" on
# re-init).  Storing module references on the built-in `sys` object keeps
# them alive across cleanups; _pandas_cache_restore re-injects them before
# each handler call so that `from shared import ...` finds pandas cached.
def _pandas_cache_bootstrap() -> None:
    if hasattr(sys, "_csv_preview_pd_cache"):
        return
    import numpy  # noqa: F401
    import pandas  # noqa: F401

    sys._csv_preview_pd_cache = {  # type: ignore[attr-defined]
        k: v
        for k, v in sys.modules.items()
        if k in ("numpy", "pandas") or k.startswith(("numpy.", "pandas."))
    }


def _pandas_cache_restore() -> None:
    for name, mod in getattr(sys, "_csv_preview_pd_cache", {}).items():
        if name not in sys.modules:
            sys.modules[name] = mod


_pandas_cache_bootstrap()


class CSVPreviewRequest(BaseModel):
    csv_path: str
    config_path: str
    automation_type: Literal["tts", "faq", "script"] = "tts"


@router.post("/csv/preview")
async def preview_csv(request: CSVPreviewRequest) -> dict:
    try:
        _pandas_cache_restore()
        from shared import load_csv, load_jsonc

        config_path = Path(request.config_path)
        if not config_path.is_absolute():
            config_path = _REPO_ROOT / config_path
        if not config_path.exists():
            raise HTTPException(
                status_code=404, detail=f"Config not found: {request.config_path}"
            )

        csv_path = Path(request.csv_path)
        if not csv_path.is_absolute():
            csv_path = _REPO_ROOT / csv_path
        if not csv_path.exists():
            raise HTTPException(
                status_code=404, detail=f"CSV not found: {request.csv_path}"
            )

        config_data = load_jsonc(str(config_path))
        df = load_csv(str(csv_path), _logger)

        max_preview_rows = 200
        all_rows: list[dict[str, str]] = []
        total_rows = 0
        num_products = 0
        estimated_versions = 0
        version_names: list[str] = []

        if request.automation_type == "tts":
            try:
                from auto_tts import ClientConfig, parse_csv_data

                config = ClientConfig(**config_data)
            except TypeError as exc:
                raise HTTPException(
                    status_code=422, detail=f"Config mismatch for tts: {exc}"
                ) from exc

            versions = parse_csv_data(df, config, _logger)
            total_rows = sum(len(v.scripts) for v in versions)
            num_products = len({v.product_number for v in versions})
            estimated_versions = len(versions)
            version_names = [v.name for v in versions]

            for version in versions:
                for i, script in enumerate(version.scripts):
                    all_rows.append(
                        {
                            "no": version.product_number,
                            "product_name": (
                                version.products[0] if version.products else ""
                            ),
                            "script": script[:100],
                            "audio_code": (
                                version.audio_codes[i]
                                if i < len(version.audio_codes)
                                else ""
                            ),
                        }
                    )

        elif request.automation_type == "faq":
            try:
                from auto_faq import FAQConfig, parse_faq_csv

                config = FAQConfig(**config_data)
            except TypeError as exc:
                raise HTTPException(
                    status_code=422, detail=f"Config mismatch for faq: {exc}"
                ) from exc

            products = parse_faq_csv(df, config, _logger)
            total_rows = sum(len(p.rows) for p in products)
            num_products = len(products)
            estimated_versions = len(products)

            for product in products:
                for row in product.rows:
                    all_rows.append(
                        {
                            "no": str(product.product_number),
                            "product_name": product.product_name,
                            "script": row.question[:100],
                            "audio_code": row.audio_code,
                        }
                    )

        else:
            try:
                from auto_script import ScriptConfig, parse_script_csv

                config = ScriptConfig(**config_data)
            except TypeError as exc:
                raise HTTPException(
                    status_code=422, detail=f"Config mismatch for script: {exc}"
                ) from exc

            products = parse_script_csv(df, config, _logger)
            total_rows = sum(len(p.rows) for p in products)
            num_products = len(products)
            estimated_versions = len(products)

            for product in products:
                for row in product.rows:
                    all_rows.append(
                        {
                            "no": str(product.product_number),
                            "product_name": product.product_name,
                            "script": row.script_content[:100],
                            "audio_code": row.audio_code,
                        }
                    )

        capped = len(all_rows) > max_preview_rows
        preview_rows = all_rows[:max_preview_rows]

        result: dict = {
            "rows": total_rows,
            "products": num_products,
            "estimated_versions": estimated_versions,
            "preview": preview_rows,
            "capped": capped,
            "errors": [],
        }
        if version_names:
            result["version_names"] = version_names

        return result

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
