"""
File: test_local_data_safety_script.py
Path: tests/modules/unknown/test_local_data_safety_script.py
Role: Validates local SQLite backup/restore/validate release helper script.
Used By:
 - pytest
Depends On:
 - scripts/release/local_data_safety.py
 - src/api/app.py
Notes:
 - Uses temporary file-system paths to keep tests isolated and deterministic.
"""

from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
from pathlib import Path

from src.api.app import create_app
from src.persistence.adapters.sqlite import SQLiteCheckpointStore
from src.tools.byoc.sqlite_store import SQLiteByocJobQueueStore, SQLiteByocResultStore, SQLiteReplayGuard


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "release" / "local_data_safety.py"


def _load_module(module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_local_data_safety_backup_restore_validate_flow(tmp_path: Path, monkeypatch) -> None:
    module = _load_module("local_data_safety_script")
    db_path = tmp_path / ".exo_data" / "exo.db"
    backup_path = tmp_path / "backup.db"
    restored_path = tmp_path / "restored.db"
    backup_meta = tmp_path / "backup-meta.json"
    validate_meta = tmp_path / "validate-meta.json"

    monkeypatch.setenv("EXO_DB_PATH", str(db_path))
    create_app()
    SQLiteCheckpointStore(db_path)
    SQLiteByocJobQueueStore(str(db_path))
    SQLiteByocResultStore(str(db_path))
    SQLiteReplayGuard(str(db_path))

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "local_data_safety.py",
            "backup",
            "--db",
            str(db_path),
            "--out",
            str(backup_path),
            "--meta-out",
            str(backup_meta),
        ],
    )
    assert module.main() == 0
    assert backup_path.exists()
    backup_payload = json.loads(backup_meta.read_text(encoding="utf-8"))
    assert backup_payload["operation"] == "backup"
    assert backup_payload["sha256"]

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "local_data_safety.py",
            "restore",
            "--in",
            str(backup_path),
            "--db",
            str(restored_path),
            "--force",
        ],
    )
    assert module.main() == 0
    assert restored_path.exists()

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "local_data_safety.py",
            "validate",
            "--db",
            str(restored_path),
            "--meta-out",
            str(validate_meta),
        ],
    )
    assert module.main() == 0
    validate_payload = json.loads(validate_meta.read_text(encoding="utf-8"))
    assert validate_payload["operation"] == "validate"
    assert validate_payload["ok"] is True
    assert validate_payload["missing_required_tables"] == []


def test_local_data_safety_validate_fails_when_required_tables_missing(tmp_path: Path, monkeypatch) -> None:
    module = _load_module("local_data_safety_script_missing")
    bad_db = tmp_path / "bad.db"
    with sqlite3.connect(str(bad_db)) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS demo_only (id INTEGER PRIMARY KEY)")
        conn.commit()

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "local_data_safety.py",
            "validate",
            "--db",
            str(bad_db),
        ],
    )
    assert module.main() == 1
