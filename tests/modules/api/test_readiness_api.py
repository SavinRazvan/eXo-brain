"""
File: test_readiness_api.py
Path: tests/modules/api/test_readiness_api.py
Role: Smoke tests for /health and /ready system probes.
Used By:
 - pytest
Depends On:
 - src/api/app.py
Notes:
 - Uses the default sqlite-backed bootstrap from create_app().
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app
from src.api import readiness as readiness_mod
from src.persistence.adapters.sqlite_audit import SQLiteAuditStore


@pytest.fixture()
def _isolated_exo_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXO_DB_PATH", str(tmp_path / "exo.db"))


def test_health_is_liveness_ok(_isolated_exo_db: None) -> None:
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body.get("status") == "ok"
    assert body.get("probe") == "liveness"


def test_ready_reports_sqlite_ok(_isolated_exo_db: None) -> None:
    client = TestClient(create_app())
    response = client.get("/ready")
    assert response.status_code == 200
    body = response.json()
    assert body.get("ready") is True
    checks = body.get("checks")
    assert isinstance(checks, dict)
    assert checks.get("primary_sqlite") == "ok"


def test_sqlite_quick_check_skips_empty_and_memory_path() -> None:
    ok, detail = readiness_mod._sqlite_quick_check("")
    assert ok is True and detail == "skipped_memory"
    ok2, detail2 = readiness_mod._sqlite_quick_check(":memory:")
    assert ok2 is True and detail2 == "skipped_memory"


def test_sqlite_quick_check_no_result_from_pragma() -> None:
    with patch.object(readiness_mod.sqlite3, "connect") as mock_connect:
        mock_ctx = MagicMock()
        mock_connect.return_value.__enter__.return_value = mock_ctx
        mock_ctx.execute.return_value.fetchone.return_value = None
        ok, detail = readiness_mod._sqlite_quick_check("/tmp/fake-readiness.db")
    assert ok is False and detail == "no_result"


def test_sqlite_quick_check_bad_pragma_message() -> None:
    with patch.object(readiness_mod.sqlite3, "connect") as mock_connect:
        mock_ctx = MagicMock()
        mock_connect.return_value.__enter__.return_value = mock_ctx
        mock_ctx.execute.return_value.fetchone.return_value = ("corrupt tree",)
        ok, detail = readiness_mod._sqlite_quick_check("/tmp/fake-readiness.db")
    assert ok is False and detail == "corrupt tree"


def test_sqlite_quick_check_os_error() -> None:
    with patch.object(readiness_mod.sqlite3, "connect", side_effect=OSError("eacces")):
        ok, detail = readiness_mod._sqlite_quick_check("/root/denied.db")
    assert ok is False and detail.startswith("os_error:")


def test_sqlite_quick_check_sqlite_error() -> None:
    import sqlite3

    with patch.object(readiness_mod.sqlite3, "connect") as mock_connect:
        mock_ctx = MagicMock()
        mock_connect.return_value.__enter__.return_value = mock_ctx
        mock_ctx.execute.side_effect = sqlite3.DatabaseError("bad")
        ok, detail = readiness_mod._sqlite_quick_check("/tmp/x.db")
    assert ok is False and detail.startswith("sqlite_error:")


def test_readiness_snapshot_non_sqlite_session_store_class_name() -> None:
    class _NonSqliteSessionStore:
        pass

    app = SimpleNamespace(
        state=SimpleNamespace(
            session_store=_NonSqliteSessionStore(),
            run_control_registry=None,
            audit_store=None,
        )
    )
    snap = readiness_mod.readiness_snapshot(app)
    assert snap["ready"] is True
    assert snap["checks"]["session_store"] == "_NonSqliteSessionStore"


def test_readiness_snapshot_includes_audit_sqlite_when_present(tmp_path: Path) -> None:
    from src.core.run_control_registry import SQLiteRunControlRegistry

    db = tmp_path / "exo.db"
    audit_db = tmp_path / "audit.db"
    app = SimpleNamespace(
        state=SimpleNamespace(
            session_store=None,
            run_control_registry=SQLiteRunControlRegistry(str(db)),
            audit_store=SQLiteAuditStore(audit_db),
        )
    )
    snap = readiness_mod.readiness_snapshot(app)
    assert snap["ready"] is True
    assert snap["checks"].get("audit_sqlite") == "ok"
