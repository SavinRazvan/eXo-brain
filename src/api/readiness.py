"""
File: readiness.py
Path: src/api/readiness.py
Role: Readiness probes for orchestrator wiring and SQLite persistence reachability.
Used By:
 - src/api/app.py
Depends On:
 - sqlite3
Notes:
 - Liveness stays on /health; /ready fails closed when configured SQLite paths are unhealthy.
 - Uses `application.state` directly; listed in `ALLOWED_APP_STATE_FILES` (see `validate_layers.py`).
"""

from __future__ import annotations

import sqlite3
from typing import Any


def _sqlite_quick_check(db_path: str) -> tuple[bool, str]:
    path = str(db_path or "").strip()
    if not path or path == ":memory:":
        return True, "skipped_memory"
    try:
        with sqlite3.connect(path, timeout=5.0) as conn:
            row = conn.execute("PRAGMA quick_check").fetchone()
            if row is None:
                return False, "no_result"
            msg = str(row[0])
            if msg.lower() == "ok":
                return True, "ok"
            return False, msg
    except OSError as exc:
        return False, f"os_error:{exc}"
    except sqlite3.Error as exc:
        return False, f"sqlite_error:{exc}"


def readiness_snapshot(application: Any) -> dict[str, object]:
    """Return structured readiness status for the fully bootstrapped application."""
    checks: dict[str, str] = {}
    all_ok = True
    state = application.state

    session_store = state.session_store
    if session_store is not None:
        cls_name = type(session_store).__name__
        if cls_name.startswith("SQLite"):
            path = getattr(session_store, "_db_path", "")
            ok, detail = _sqlite_quick_check(str(path))
            checks["primary_sqlite"] = detail
            all_ok = all_ok and ok
        else:
            checks["session_store"] = cls_name

    registry = state.run_control_registry
    if registry is not None and type(registry).__name__ == "SQLiteRunControlRegistry":
        path = getattr(registry, "_db_path", "")
        ok, detail = _sqlite_quick_check(str(path))
        checks["control_state_sqlite"] = detail
        all_ok = all_ok and ok

    audit_store = state.audit_store
    if audit_store is not None and type(audit_store).__name__ == "SQLiteAuditStore":
        path = getattr(audit_store, "_db_path", "")
        ok, detail = _sqlite_quick_check(str(path))
        checks["audit_sqlite"] = detail
        all_ok = all_ok and ok

    return {"ready": all_ok, "checks": checks}
