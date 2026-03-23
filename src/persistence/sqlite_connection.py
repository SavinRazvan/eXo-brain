"""
File: sqlite_connection.py
Path: src/persistence/sqlite_connection.py
Role: Shared SQLite connection helpers for file-backed stores (WAL, timeouts).
Used By:
 - src/core/run_control_registry.py
 - src/tenancy/rate_limiter.py
 - src/persistence/adapters/sqlite_audit.py
Depends On:
 - sqlite3
Notes:
 - WAL improves multi-reader / single-writer concurrency for control-plane hot paths.
 - check_same_thread=False allows asyncio.to_thread writers on the same path.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path


def open_sqlite_file(
    db_path: str | Path,
    *,
    timeout_seconds: float = 30.0,
    row_factory: type | None = sqlite3.Row,
) -> sqlite3.Connection:
    """Open a SQLite file connection tuned for control-plane style workloads."""
    path = str(db_path)
    conn = sqlite3.connect(path, timeout=timeout_seconds, check_same_thread=False)
    if row_factory is not None:
        conn.row_factory = row_factory
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn
