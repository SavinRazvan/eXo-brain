"""
File: rate_limiter.py
Path: src/tenancy/rate_limiter.py
Role: Process-local per-tenant fixed-window rate limiting.
Used By:
 - src/api/bootstrap.py
 - src/api/routers/tools.py
 - src/api/routers/turns.py
Depends On:
 - threading
 - time
Notes:
 - This limiter is intentionally simple and deterministic for local/runtime control paths.
"""

from __future__ import annotations

import threading
import time
import sqlite3

from src.persistence.sqlite_connection import open_sqlite_file


class TenantRateLimiter:
    def __init__(self, *, max_requests: int, window_seconds: int = 60) -> None:
        self._max_requests = max(int(max_requests), 0)
        self._window_seconds = max(int(window_seconds), 1)
        self._lock = threading.Lock()
        self._windows: dict[str, tuple[int, int]] = {}

    def allow(self, tenant_id: str) -> tuple[bool, int]:
        if self._max_requests <= 0:
            return True, 0
        tenant_key = str(tenant_id or "default").strip() or "default"
        now = int(time.time())
        current_window = now // self._window_seconds
        with self._lock:
            window, count = self._windows.get(tenant_key, (current_window, 0))
            if window != current_window:
                window = current_window
                count = 0
            if count >= self._max_requests:
                return False, self._window_seconds
            self._windows[tenant_key] = (window, count + 1)
            return True, max(self._max_requests - (count + 1), 0)


class SQLiteTenantRateLimiter:
    """SQLite-backed fixed-window limiter for shared multi-process admission checks."""

    def __init__(
        self,
        *,
        db_path: str,
        max_requests: int,
        window_seconds: int = 60,
        limiter_id: str = "default",
    ) -> None:
        self._db_path = db_path
        self._max_requests = max(int(max_requests), 0)
        self._window_seconds = max(int(window_seconds), 1)
        self._limiter_id = str(limiter_id or "default").strip() or "default"
        self._lock = threading.Lock()
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        return open_sqlite_file(self._db_path)

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tenant_rate_windows (
                    tenant_id TEXT NOT NULL,
                    limiter_id TEXT NOT NULL,
                    window_id INTEGER NOT NULL,
                    request_count INTEGER NOT NULL,
                    updated_at_epoch INTEGER NOT NULL,
                    PRIMARY KEY (tenant_id, limiter_id)
                )
                """
            )

    def allow(self, tenant_id: str, *, limiter_id: str | None = None) -> tuple[bool, int]:
        if self._max_requests <= 0:
            return True, 0
        tenant_key = str(tenant_id or "default").strip() or "default"
        limiter_key = str(limiter_id or self._limiter_id).strip() or self._limiter_id
        now = int(time.time())
        current_window = now // self._window_seconds
        with self._lock, self._conn() as conn:
            row = conn.execute(
                """
                SELECT window_id, request_count
                FROM tenant_rate_windows
                WHERE tenant_id = ? AND limiter_id = ?
                """,
                (tenant_key, limiter_key),
            ).fetchone()
            if row is None or int(row["window_id"]) != current_window:
                request_count = 0
            else:
                request_count = int(row["request_count"])
            if request_count >= self._max_requests:
                return False, self._window_seconds
            new_count = request_count + 1
            conn.execute(
                """
                INSERT OR REPLACE INTO tenant_rate_windows (
                    tenant_id, limiter_id, window_id, request_count, updated_at_epoch
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (tenant_key, limiter_key, current_window, new_count, now),
            )
            return True, max(self._max_requests - new_count, 0)
