"""
File: byoc_fairness.py
Path: src/policies/byoc_fairness.py
Role: Deterministic fair-admission coordinator for BYOC cross-tenant contention.
Used By:
 - src/tools/byoc/connector_runtime.py
Depends On:
 - dataclasses
 - threading
Notes:
 - Advisory/runtime policy only; no provider-specific branching.
"""

from __future__ import annotations

from dataclasses import dataclass
import sqlite3
import threading
import time


@dataclass(frozen=True)
class FairAdmissionToken:
    tenant_id: str
    request_id: int


@dataclass
class _PendingAdmission:
    tenant_id: str
    request_id: int
    granted: bool = False


def _pick_next_tenant(
    pending: list[_PendingAdmission],
    grants_total: dict[str, int],
) -> str | None:
    if not pending:
        return None
    first_seq: dict[str, int] = {}
    for item in pending:
        first_seq.setdefault(item.tenant_id, item.request_id)
    tenants = list(first_seq.keys())
    tenants.sort(
        key=lambda tenant_id: (
            int(grants_total.get(tenant_id, 0)),
            int(first_seq.get(tenant_id, 0)),
            str(tenant_id),
        )
    )
    return tenants[0] if tenants else None


class ByocFairAdmissionCoordinator:
    """Process-local fair admission coordinator with deterministic tie-breaks."""

    def __init__(self, *, max_inflight_global: int) -> None:
        self._max_inflight_global = max(int(max_inflight_global), 1)
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)
        self._next_request_id = 0
        self._pending: list[_PendingAdmission] = []
        self._inflight_by_tenant: dict[str, int] = {}
        self._grants_total: dict[str, int] = {}
        self._inflight_total = 0

    def acquire(self, *, tenant_id: str, wait_timeout_ms: int) -> FairAdmissionToken | None:
        normalized = str(tenant_id).strip() or "default"
        timeout_s = max(int(wait_timeout_ms), 1) / 1000.0
        deadline = time.monotonic() + timeout_s
        with self._condition:
            self._next_request_id += 1
            request = _PendingAdmission(tenant_id=normalized, request_id=self._next_request_id)
            self._pending.append(request)
            while True:
                self._try_grant_unlocked()
                if request.granted:
                    return FairAdmissionToken(tenant_id=normalized, request_id=request.request_id)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self._pending = [item for item in self._pending if item.request_id != request.request_id]
                    return None
                self._condition.wait(timeout=remaining)

    def release(self, token: FairAdmissionToken) -> None:
        with self._condition:
            tenant = str(token.tenant_id).strip() or "default"
            if self._inflight_total > 0:
                self._inflight_total -= 1
            active = int(self._inflight_by_tenant.get(tenant, 0))
            if active <= 1:
                self._inflight_by_tenant.pop(tenant, None)
            else:
                self._inflight_by_tenant[tenant] = active - 1
            self._try_grant_unlocked()
            self._condition.notify_all()

    def stats(self) -> dict[str, int]:
        with self._lock:
            return {
                "fair_admission_max_inflight_global": int(self._max_inflight_global),
                "fair_admission_inflight_total": int(self._inflight_total),
                "fair_admission_pending_total": int(len(self._pending)),
            }

    def _try_grant_unlocked(self) -> None:
        while self._inflight_total < self._max_inflight_global and self._pending:
            next_tenant = _pick_next_tenant(self._pending, self._grants_total)
            if not next_tenant:
                break
            idx = -1
            for pos, item in enumerate(self._pending):
                if item.tenant_id == next_tenant:
                    idx = pos
                    break
            if idx < 0:
                break
            item = self._pending.pop(idx)
            item.granted = True
            self._inflight_total += 1
            self._inflight_by_tenant[next_tenant] = int(self._inflight_by_tenant.get(next_tenant, 0)) + 1
            self._grants_total[next_tenant] = int(self._grants_total.get(next_tenant, 0)) + 1
            self._condition.notify_all()


class SQLiteByocFairAdmissionCoordinator:
    """SQLite-backed global inflight coordinator for multi-process fairness admission."""

    def __init__(self, *, db_path: str, max_inflight_global: int, lease_seconds: int = 30) -> None:
        self._db_path = db_path
        self._max_inflight_global = max(int(max_inflight_global), 1)
        self._lease_seconds = max(int(lease_seconds), 1)
        self._lock = threading.Lock()
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS byoc_fair_admission_slots (
                    slot_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id TEXT NOT NULL,
                    acquired_at_epoch INTEGER NOT NULL,
                    expires_at_epoch INTEGER NOT NULL,
                    released INTEGER NOT NULL DEFAULT 0
                )
                """
            )

    def _cleanup_expired(self, conn: sqlite3.Connection, now: int) -> None:
        conn.execute(
            """
            DELETE FROM byoc_fair_admission_slots
            WHERE released = 1 OR expires_at_epoch <= ?
            """,
            (now,),
        )

    def acquire(self, *, tenant_id: str, wait_timeout_ms: int) -> FairAdmissionToken | None:
        normalized = str(tenant_id).strip() or "default"
        timeout_s = max(int(wait_timeout_ms), 1) / 1000.0
        deadline = time.monotonic() + timeout_s
        while True:
            now = int(time.time())
            with self._lock, self._conn() as conn:
                self._cleanup_expired(conn, now)
                row = conn.execute(
                    "SELECT COUNT(*) AS c FROM byoc_fair_admission_slots WHERE released = 0"
                ).fetchone()
                inflight = int(row["c"]) if row is not None else 0
                if inflight < self._max_inflight_global:
                    cur = conn.execute(
                        """
                        INSERT INTO byoc_fair_admission_slots (tenant_id, acquired_at_epoch, expires_at_epoch, released)
                        VALUES (?, ?, ?, 0)
                        """,
                        (normalized, now, now + self._lease_seconds),
                    )
                    return FairAdmissionToken(tenant_id=normalized, request_id=int(cur.lastrowid))
            if time.monotonic() >= deadline:
                return None
            time.sleep(0.01)

    def release(self, token: FairAdmissionToken) -> None:
        with self._lock, self._conn() as conn:
            conn.execute(
                "UPDATE byoc_fair_admission_slots SET released = 1 WHERE slot_id = ?",
                (int(token.request_id),),
            )
            self._cleanup_expired(conn, int(time.time()))

    def stats(self) -> dict[str, int]:
        now = int(time.time())
        with self._lock, self._conn() as conn:
            self._cleanup_expired(conn, now)
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM byoc_fair_admission_slots WHERE released = 0"
            ).fetchone()
            inflight = int(row["c"]) if row is not None else 0
        return {
            "fair_admission_max_inflight_global": int(self._max_inflight_global),
            "fair_admission_inflight_total": int(inflight),
            "fair_admission_pending_total": 0,
        }
