"""SQLite-based history storage for automation runs."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_DB_PATH: Optional[Path] = None


def init_db(app_data_dir: Path) -> None:
    """Initialize the SQLite database in the app data directory."""
    global _DB_PATH
    db_dir = app_data_dir / "history"
    db_dir.mkdir(parents=True, exist_ok=True)
    _DB_PATH = db_dir / "runs.db"
    _create_tables()


def _get_db_path() -> Path:
    """Get the database path, using a temp path if not initialized."""
    if _DB_PATH is None:
        return Path(":memory:")
    return _DB_PATH


def _create_tables() -> None:
    """Create the runs table if it doesn't exist."""
    db_path = _get_db_path()
    if str(db_path) == ":memory:":
        return
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY,
                automation_type TEXT NOT NULL,
                client TEXT NOT NULL DEFAULT 'default',
                status TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                versions_total INTEGER DEFAULT 0,
                versions_success INTEGER DEFAULT 0,
                versions_failed INTEGER DEFAULT 0,
                error TEXT,
                report_json TEXT,
                csv_file TEXT
            )
        """
        )
        conn.commit()

        # Migrate existing databases: add csv_file column if missing
        try:
            conn.execute("ALTER TABLE runs ADD COLUMN csv_file TEXT")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # Column already exists


def save_run(job: object) -> str:
    """Save a completed job to history. Returns the run ID."""
    db_path = _get_db_path()
    run_id = str(uuid.uuid4())

    report = {
        "job_id": getattr(job, "job_id", None),
        "automation_type": (
            job.automation_type.value  # type: ignore[union-attr]
            if hasattr(job.automation_type, "value")  # type: ignore[union-attr]
            else str(getattr(job, "automation_type", ""))
        ),
        "status": (
            job.status.value  # type: ignore[union-attr]
            if hasattr(job.status, "value")  # type: ignore[union-attr]
            else str(getattr(job, "status", ""))
        ),
    }

    if str(db_path) == ":memory:":
        return run_id

    automation_type = (
        job.automation_type.value  # type: ignore[union-attr]
        if hasattr(job.automation_type, "value")  # type: ignore[union-attr]
        else str(getattr(job, "automation_type", ""))
    )
    status = (
        job.status.value  # type: ignore[union-attr]
        if hasattr(job.status, "value")  # type: ignore[union-attr]
        else str(getattr(job, "status", ""))
    )
    progress = getattr(job, "progress", None)
    total = progress.total if progress else 0
    current = progress.current if progress else 0
    # If job succeeded, all versions that were processed are successes
    # If failed, current - 1 succeeded and 1 failed (the one that caused the error)
    if status == "success":
        versions_success = total
        versions_failed = 0
    elif status == "failed" and current > 0:
        versions_success = max(0, current - 1)
        versions_failed = 1
    else:
        versions_success = current
        versions_failed = 0

    # Use actual client from job options if available
    client_name = getattr(job, "config_path", "default")
    if "/" in client_name:
        parts = client_name.replace("\\", "/").split("/")
        for i, part in enumerate(parts):
            if part == "configs" and i + 1 < len(parts):
                client_name = parts[i + 1]
                break

    csv_file = None
    raw_csv_path = getattr(job, "csv_path", None)
    if raw_csv_path:
        csv_file = Path(raw_csv_path).name

    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            """
            INSERT INTO runs (id, automation_type, client, status, started_at, finished_at,
                              versions_total, versions_success, versions_failed, error, report_json, csv_file)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                automation_type,
                client_name,
                status,
                getattr(job, "started_at", datetime.now(timezone.utc).isoformat()),
                getattr(job, "finished_at", None),
                total,
                versions_success,
                versions_failed,
                getattr(job, "error", None),
                json.dumps(report),
                csv_file,
            ),
        )
        conn.commit()

    return run_id


def get_runs(
    limit: int = 50,
    offset: int = 0,
    type_filter: Optional[str] = None,
) -> list[dict]:
    """Get paginated list of past runs."""
    db_path = _get_db_path()
    if str(db_path) == ":memory:":
        return []

    query = "SELECT * FROM runs"
    params: list = []

    if type_filter:
        query += " WHERE automation_type = ?"
        params.append(type_filter)

    query += " ORDER BY started_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]


def get_run(run_id: str) -> Optional[dict]:
    """Get a single run by ID."""
    db_path = _get_db_path()
    if str(db_path) == ":memory:":
        return None

    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        return dict(row) if row else None
