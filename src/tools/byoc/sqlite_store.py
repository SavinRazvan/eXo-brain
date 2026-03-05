"""
File: sqlite_store.py
Path: src/tools/byoc/sqlite_store.py
Role: SQLite-backed BYOC queue/result/replay stores for restart-durable pull-worker flows.
Used By:
 - src/runtime/tenant_runtime.py
 - tests/modules/tools/test_byoc_sqlite_recovery.py
Depends On:
 - sqlite3
 - src/tools/byoc/job_store.py
 - src/tools/byoc/result_store.py
Notes:
 - Uses file-backed SQLite by default; `:memory:` keeps one shared connection per store instance.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid

from src.tools.byoc.job_contracts import ByocToolJobEnvelope, ByocToolResultEnvelope
from src.tools.byoc.job_store import ByocJobQueueStore, JobLeaseClaim
from src.tools.byoc.result_store import (
    ByocResultConflictStrategy,
    ByocResultIngestOutcome,
    ByocResultStore,
    ReplayGuard,
    resolve_result_conflict,
)


class _SQLiteStoreMixin:
    def __init__(self, db_path: str) -> None:
        self._db_path = str(db_path)
        self._shared_conn: sqlite3.Connection | None = (
            sqlite3.connect(":memory:", check_same_thread=False)
            if self._db_path == ":memory:"
            else None
        )
        self._lock = threading.Lock()

    def _connect(self) -> sqlite3.Connection:
        if self._shared_conn is not None:
            return self._shared_conn
        return sqlite3.connect(self._db_path)

    @staticmethod
    def _has_column(conn: sqlite3.Connection, table_name: str, column_name: str) -> bool:
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        return any(str(row[1]) == str(column_name) for row in rows)


class SQLiteByocJobQueueStore(_SQLiteStoreMixin, ByocJobQueueStore):
    """SQLite-backed durable BYOC job queue with lease/requeue semantics."""

    def __init__(self, db_path: str) -> None:
        super().__init__(db_path)
        self._ensure_schema()

    def enqueue(self, job: ByocToolJobEnvelope) -> None:
        with self._lock:
            conn = self._connect()
            conn.execute(
                """
                INSERT OR IGNORE INTO byoc_jobs (
                    job_id, tenant_id, run_id, call_id, tool_name, arguments_json, timeout_ms,
                    correlation_id, idempotency_key, status, leased_by_worker_id, lease_token,
                    lease_expires_at_epoch, claim_attempt, completed_at_epoch, cancelled_at_epoch,
                    tool_version, package_ref, entry_file, entrypoint,
                    artifact_bundle_hash_sha256, artifact_bundle_signature_hmac_sha256, artifact_signature_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'queued', '', '', 0, 0, 0, 0, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job.job_id,
                    job.tenant_id,
                    job.run_id,
                    job.call_id,
                    job.tool_name,
                    json.dumps(job.arguments),
                    int(job.timeout_ms),
                    job.correlation_id,
                    job.idempotency_key,
                    job.tool_version,
                    job.package_ref,
                    job.entry_file,
                    job.entrypoint,
                    job.artifact_bundle_hash_sha256,
                    job.artifact_bundle_signature_hmac_sha256,
                    job.artifact_signature_version,
                ),
            )
            conn.commit()

    def claim_next(self, *, tenant_id: str, worker_id: str, lease_ttl_seconds: int) -> JobLeaseClaim | None:
        now = time.time()
        ttl = max(int(lease_ttl_seconds), 1)
        with self._lock:
            self._requeue_expired_leases_unlocked(now)
            conn = self._connect()
            row = conn.execute(
                """
                SELECT job_id, tenant_id, run_id, call_id, tool_name, arguments_json, timeout_ms,
                       correlation_id, idempotency_key, claim_attempt,
                       tool_version, package_ref, entry_file, entrypoint,
                       artifact_bundle_hash_sha256, artifact_bundle_signature_hmac_sha256, artifact_signature_version
                FROM byoc_jobs
                WHERE tenant_id = ? AND status = 'queued'
                ORDER BY rowid ASC
                LIMIT 1
                """,
                (tenant_id,),
            ).fetchone()
            if row is None:
                return None
            lease_token = f"lease_{uuid.uuid4().hex[:12]}"
            lease_expires = now + ttl
            claim_attempt = int(row[9]) + 1
            conn.execute(
                """
                UPDATE byoc_jobs
                SET status = 'leased',
                    leased_by_worker_id = ?,
                    lease_token = ?,
                    lease_expires_at_epoch = ?,
                    claim_attempt = ?
                WHERE job_id = ?
                """,
                (worker_id, lease_token, lease_expires, claim_attempt, row[0]),
            )
            conn.commit()
            envelope = ByocToolJobEnvelope(
                job_id=str(row[0]),
                tenant_id=str(row[1]),
                run_id=str(row[2]),
                call_id=str(row[3]),
                tool_name=str(row[4]),
                arguments=json.loads(str(row[5])),
                timeout_ms=int(row[6]),
                correlation_id=str(row[7]),
                idempotency_key=str(row[8]),
                lease_token=lease_token,
                lease_expires_at_epoch=int(lease_expires),
                claim_attempt=claim_attempt,
                tool_version=str(row[10]),
                package_ref=str(row[11]),
                entry_file=str(row[12]),
                entrypoint=str(row[13]),
                artifact_bundle_hash_sha256=str(row[14]),
                artifact_bundle_signature_hmac_sha256=str(row[15]),
                artifact_signature_version=str(row[16]),
            )
            return JobLeaseClaim(job=envelope)

    def complete_claim(self, *, job_id: str, lease_token: str) -> bool:
        with self._lock:
            conn = self._connect()
            now = time.time()
            row = conn.execute(
                """
                SELECT status, lease_token, lease_expires_at_epoch
                FROM byoc_jobs
                WHERE job_id = ?
                """,
                (job_id,),
            ).fetchone()
            if row is None:
                return False
            status, active_token, lease_expires = row
            if status != "leased":
                return False
            if float(lease_expires) <= now:
                self._requeue_expired_leases_unlocked(now)
                return False
            if str(active_token) != str(lease_token):
                return False
            conn.execute(
                "UPDATE byoc_jobs SET status = 'completed', completed_at_epoch = ?, cancelled_at_epoch = 0 WHERE job_id = ?",
                (now, job_id),
            )
            conn.commit()
            return True

    def get_leased_job(self, *, job_id: str, lease_token: str) -> ByocToolJobEnvelope | None:
        with self._lock:
            conn = self._connect()
            now = time.time()
            row = conn.execute(
                """
                SELECT job_id, tenant_id, run_id, call_id, tool_name, arguments_json, timeout_ms,
                       correlation_id, idempotency_key, claim_attempt,
                       lease_token, lease_expires_at_epoch, status,
                       tool_version, package_ref, entry_file, entrypoint,
                       artifact_bundle_hash_sha256, artifact_bundle_signature_hmac_sha256, artifact_signature_version
                FROM byoc_jobs
                WHERE job_id = ?
                """,
                (job_id,),
            ).fetchone()
            if row is None:
                return None
            active_lease_token = str(row[10])
            lease_expires = float(row[11])
            status = str(row[12])
            if status != "leased":
                return None
            if lease_expires <= now:
                self._requeue_expired_leases_unlocked(now)
                return None
            if active_lease_token != str(lease_token):
                return None
            return ByocToolJobEnvelope(
                job_id=str(row[0]),
                tenant_id=str(row[1]),
                run_id=str(row[2]),
                call_id=str(row[3]),
                tool_name=str(row[4]),
                arguments=json.loads(str(row[5])),
                timeout_ms=int(row[6]),
                correlation_id=str(row[7]),
                idempotency_key=str(row[8]),
                claim_attempt=int(row[9]),
                lease_token=active_lease_token,
                lease_expires_at_epoch=int(lease_expires),
                tool_version=str(row[13]),
                package_ref=str(row[14]),
                entry_file=str(row[15]),
                entrypoint=str(row[16]),
                artifact_bundle_hash_sha256=str(row[17]),
                artifact_bundle_signature_hmac_sha256=str(row[18]),
                artifact_signature_version=str(row[19]),
            )

    def requeue_expired_leases(self, *, max_claim_attempts_before_dlq: int | None = None) -> int:
        with self._lock:
            return self._requeue_expired_leases_unlocked(
                time.time(),
                max_claim_attempts_before_dlq=max_claim_attempts_before_dlq,
            )

    def cancel_pending_call(self, *, call_id: str) -> int:
        normalized = str(call_id).strip()
        if not normalized:
            return 0
        with self._lock:
            conn = self._connect()
            cursor = conn.execute(
                """
                UPDATE byoc_jobs
                SET status = 'cancelled',
                    cancelled_at_epoch = ?
                WHERE call_id = ? AND status = 'queued'
                """,
                (time.time(), normalized),
            )
            affected = max(int(cursor.rowcount), 0)
            conn.execute(
                """
                UPDATE byoc_jobs
                SET lease_expires_at_epoch = 0
                WHERE call_id = ? AND status = 'leased'
                """,
                (normalized,),
            )
            conn.commit()
            self._requeue_expired_leases_unlocked(time.time(), max_claim_attempts_before_dlq=None)
            return affected

    def queue_depth(self) -> int:
        with self._lock:
            conn = self._connect()
            row = conn.execute(
                "SELECT COUNT(1) FROM byoc_jobs WHERE status = 'queued'"
            ).fetchone()
            return int(row[0]) if row else 0

    def dead_letter_count(self, *, tenant_id: str) -> int:
        normalized = str(tenant_id).strip()
        if not normalized:
            return 0
        with self._lock:
            conn = self._connect()
            row = conn.execute(
                "SELECT COUNT(1) FROM byoc_jobs WHERE tenant_id = ? AND status = 'dead_lettered'",
                (normalized,),
            ).fetchone()
            return int(row[0]) if row else 0

    def list_dead_letter_jobs(self, *, tenant_id: str, limit: int = 100) -> list[dict[str, str]]:
        normalized = str(tenant_id).strip()
        bounded_limit = max(1, int(limit))
        if not normalized:
            return []
        with self._lock:
            conn = self._connect()
            rows = conn.execute(
                """
                SELECT job_id, call_id, tool_name, idempotency_key, claim_attempt,
                       dead_letter_reason_code, dead_lettered_at_epoch, replay_count
                FROM byoc_jobs
                WHERE tenant_id = ? AND status = 'dead_lettered'
                ORDER BY dead_lettered_at_epoch DESC, rowid DESC
                LIMIT ?
                """,
                (normalized, bounded_limit),
            ).fetchall()
        return [
            {
                "job_id": str(row[0]),
                "call_id": str(row[1]),
                "tool_name": str(row[2]),
                "idempotency_key": str(row[3]),
                "claim_attempt": str(int(row[4])),
                "dead_letter_reason_code": str(row[5]),
                "dead_lettered_at_epoch": str(int(float(row[6]))),
                "replay_count": str(int(row[7])),
            }
            for row in rows
        ]

    def replay_dead_letter_job(self, *, tenant_id: str, job_id: str) -> bool:
        normalized_tenant = str(tenant_id).strip()
        normalized_job = str(job_id).strip()
        if not normalized_tenant or not normalized_job:
            return False
        with self._lock:
            conn = self._connect()
            row = conn.execute(
                """
                SELECT status
                FROM byoc_jobs
                WHERE tenant_id = ? AND job_id = ?
                """,
                (normalized_tenant, normalized_job),
            ).fetchone()
            if row is None or str(row[0]) != "dead_lettered":
                return False
            conn.execute(
                """
                UPDATE byoc_jobs
                SET status = 'queued',
                    leased_by_worker_id = '',
                    lease_token = '',
                    lease_expires_at_epoch = 0,
                    dead_letter_reason_code = '',
                    dead_lettered_at_epoch = 0,
                    replay_count = replay_count + 1
                WHERE tenant_id = ? AND job_id = ?
                """,
                (normalized_tenant, normalized_job),
            )
            conn.commit()
            return True

    def health_metrics(self, *, tenant_id: str) -> dict[str, int]:
        normalized = str(tenant_id).strip()
        if not normalized:
            return {
                "queued_jobs": 0,
                "leased_jobs": 0,
                "completed_jobs": 0,
                "cancelled_jobs": 0,
            }
        with self._lock:
            conn = self._connect()
            rows = conn.execute(
                """
                SELECT status, COUNT(1)
                FROM byoc_jobs
                WHERE tenant_id = ?
                GROUP BY status
                """,
                (normalized,),
            ).fetchall()
        metrics = {
            "queued_jobs": 0,
            "leased_jobs": 0,
            "completed_jobs": 0,
            "cancelled_jobs": 0,
            "dead_lettered_jobs": 0,
        }
        for status, count in rows:
            key = f"{str(status)}_jobs"
            if key in metrics:
                metrics[key] = int(count)
        return metrics

    def cleanup_retention(
        self,
        *,
        tenant_id: str,
        completed_ttl_seconds: int,
        cancelled_ttl_seconds: int,
        max_completed_records: int,
        max_cancelled_records: int,
    ) -> dict[str, int]:
        normalized = str(tenant_id).strip()
        if not normalized:
            return {"completed_pruned": 0, "cancelled_pruned": 0}
        now = time.time()
        completed_cutoff = now - max(int(completed_ttl_seconds), 1)
        cancelled_cutoff = now - max(int(cancelled_ttl_seconds), 1)
        completed_pruned = 0
        cancelled_pruned = 0
        with self._lock:
            conn = self._connect()
            completed_cursor = conn.execute(
                """
                DELETE FROM byoc_jobs
                WHERE tenant_id = ?
                  AND status = 'completed'
                  AND completed_at_epoch > 0
                  AND completed_at_epoch <= ?
                """,
                (normalized, completed_cutoff),
            )
            completed_pruned += max(int(completed_cursor.rowcount), 0)
            cancelled_cursor = conn.execute(
                """
                DELETE FROM byoc_jobs
                WHERE tenant_id = ?
                  AND status = 'cancelled'
                  AND cancelled_at_epoch > 0
                  AND cancelled_at_epoch <= ?
                """,
                (normalized, cancelled_cutoff),
            )
            cancelled_pruned += max(int(cancelled_cursor.rowcount), 0)

            completed_rows = conn.execute(
                """
                SELECT job_id
                FROM byoc_jobs
                WHERE tenant_id = ? AND status = 'completed'
                ORDER BY completed_at_epoch ASC, rowid ASC
                """,
                (normalized,),
            ).fetchall()
            cancelled_rows = conn.execute(
                """
                SELECT job_id
                FROM byoc_jobs
                WHERE tenant_id = ? AND status = 'cancelled'
                ORDER BY cancelled_at_epoch ASC, rowid ASC
                """,
                (normalized,),
            ).fetchall()
            overflow_completed = max(0, len(completed_rows) - max(int(max_completed_records), 0))
            overflow_cancelled = max(0, len(cancelled_rows) - max(int(max_cancelled_records), 0))
            for row in completed_rows[:overflow_completed]:
                conn.execute("DELETE FROM byoc_jobs WHERE job_id = ?", (str(row[0]),))
                completed_pruned += 1
            for row in cancelled_rows[:overflow_cancelled]:
                conn.execute("DELETE FROM byoc_jobs WHERE job_id = ?", (str(row[0]),))
                cancelled_pruned += 1
            conn.commit()
        return {"completed_pruned": completed_pruned, "cancelled_pruned": cancelled_pruned}

    def _requeue_expired_leases_unlocked(
        self,
        now: float,
        *,
        max_claim_attempts_before_dlq: int | None = None,
    ) -> int:
        conn = self._connect()
        if max_claim_attempts_before_dlq is not None and max_claim_attempts_before_dlq > 0:
            conn.execute(
                """
                UPDATE byoc_jobs
                SET status = 'dead_lettered',
                    leased_by_worker_id = '',
                    lease_token = '',
                    lease_expires_at_epoch = 0,
                    dead_letter_reason_code = 'BYOC_LEASE_RETRY_EXHAUSTED',
                    dead_lettered_at_epoch = ?,
                    completed_at_epoch = 0,
                    cancelled_at_epoch = 0
                WHERE status = 'leased'
                  AND lease_expires_at_epoch <= ?
                  AND claim_attempt >= ?
                """,
                (now, now, int(max_claim_attempts_before_dlq)),
            )
        conn.execute(
            """
            UPDATE byoc_jobs
            SET status = 'queued',
                leased_by_worker_id = '',
                lease_token = '',
                lease_expires_at_epoch = 0,
                completed_at_epoch = 0,
                cancelled_at_epoch = 0
            WHERE status = 'leased' AND lease_expires_at_epoch <= ?
            """,
            (now,),
        )
        changed = int(conn.total_changes)
        conn.commit()
        return changed

    def _ensure_schema(self) -> None:
        with self._lock:
            conn = self._connect()
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS byoc_jobs (
                    job_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    call_id TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    arguments_json TEXT NOT NULL,
                    timeout_ms INTEGER NOT NULL,
                    correlation_id TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    status TEXT NOT NULL,
                    leased_by_worker_id TEXT NOT NULL DEFAULT '',
                    lease_token TEXT NOT NULL DEFAULT '',
                    lease_expires_at_epoch REAL NOT NULL DEFAULT 0,
                    claim_attempt INTEGER NOT NULL DEFAULT 0,
                    completed_at_epoch REAL NOT NULL DEFAULT 0,
                    cancelled_at_epoch REAL NOT NULL DEFAULT 0,
                    dead_lettered_at_epoch REAL NOT NULL DEFAULT 0,
                    dead_letter_reason_code TEXT NOT NULL DEFAULT '',
                    replay_count INTEGER NOT NULL DEFAULT 0,
                    tool_version TEXT NOT NULL DEFAULT '',
                    package_ref TEXT NOT NULL DEFAULT '',
                    entry_file TEXT NOT NULL DEFAULT '',
                    entrypoint TEXT NOT NULL DEFAULT '',
                    artifact_bundle_hash_sha256 TEXT NOT NULL DEFAULT '',
                    artifact_bundle_signature_hmac_sha256 TEXT NOT NULL DEFAULT '',
                    artifact_signature_version TEXT NOT NULL DEFAULT ''
                )
                """
            )
            if not self._has_column(conn, "byoc_jobs", "completed_at_epoch"):
                conn.execute("ALTER TABLE byoc_jobs ADD COLUMN completed_at_epoch REAL NOT NULL DEFAULT 0")
            if not self._has_column(conn, "byoc_jobs", "cancelled_at_epoch"):
                conn.execute("ALTER TABLE byoc_jobs ADD COLUMN cancelled_at_epoch REAL NOT NULL DEFAULT 0")
            if not self._has_column(conn, "byoc_jobs", "dead_lettered_at_epoch"):
                conn.execute("ALTER TABLE byoc_jobs ADD COLUMN dead_lettered_at_epoch REAL NOT NULL DEFAULT 0")
            if not self._has_column(conn, "byoc_jobs", "dead_letter_reason_code"):
                conn.execute("ALTER TABLE byoc_jobs ADD COLUMN dead_letter_reason_code TEXT NOT NULL DEFAULT ''")
            if not self._has_column(conn, "byoc_jobs", "replay_count"):
                conn.execute("ALTER TABLE byoc_jobs ADD COLUMN replay_count INTEGER NOT NULL DEFAULT 0")
            if not self._has_column(conn, "byoc_jobs", "tool_version"):
                conn.execute("ALTER TABLE byoc_jobs ADD COLUMN tool_version TEXT NOT NULL DEFAULT ''")
            if not self._has_column(conn, "byoc_jobs", "package_ref"):
                conn.execute("ALTER TABLE byoc_jobs ADD COLUMN package_ref TEXT NOT NULL DEFAULT ''")
            if not self._has_column(conn, "byoc_jobs", "entry_file"):
                conn.execute("ALTER TABLE byoc_jobs ADD COLUMN entry_file TEXT NOT NULL DEFAULT ''")
            if not self._has_column(conn, "byoc_jobs", "entrypoint"):
                conn.execute("ALTER TABLE byoc_jobs ADD COLUMN entrypoint TEXT NOT NULL DEFAULT ''")
            if not self._has_column(conn, "byoc_jobs", "artifact_bundle_hash_sha256"):
                conn.execute(
                    "ALTER TABLE byoc_jobs ADD COLUMN artifact_bundle_hash_sha256 TEXT NOT NULL DEFAULT ''"
                )
            if not self._has_column(conn, "byoc_jobs", "artifact_bundle_signature_hmac_sha256"):
                conn.execute(
                    "ALTER TABLE byoc_jobs ADD COLUMN artifact_bundle_signature_hmac_sha256 TEXT NOT NULL DEFAULT ''"
                )
            if not self._has_column(conn, "byoc_jobs", "artifact_signature_version"):
                conn.execute(
                    "ALTER TABLE byoc_jobs ADD COLUMN artifact_signature_version TEXT NOT NULL DEFAULT ''"
                )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_byoc_jobs_tenant_status ON byoc_jobs (tenant_id, status)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_byoc_jobs_call_id ON byoc_jobs (call_id)"
            )
            conn.commit()


class SQLiteByocResultStore(_SQLiteStoreMixin, ByocResultStore):
    """SQLite-backed idempotent result store with one-shot consumption."""

    def __init__(
        self,
        db_path: str,
        *,
        conflict_strategy: ByocResultConflictStrategy = ByocResultConflictStrategy.FIRST_WRITE_WINS,
    ) -> None:
        super().__init__(db_path)
        self._conflict_strategy = conflict_strategy
        self._ensure_schema()

    def ingest(self, result: ByocToolResultEnvelope) -> ByocResultIngestOutcome:
        key = str(result.idempotency_key).strip()
        if not key:
            return ByocResultIngestOutcome(
                accepted=False,
                duplicate=False,
                reason_code="IDEMPOTENCY_KEY_REQUIRED",
            )
        payload = {
            "job_id": result.job_id,
            "tenant_id": result.tenant_id,
            "run_id": result.run_id,
            "call_id": result.call_id,
            "tool_name": result.tool_name,
            "status": result.status,
            "output": result.output,
            "error_code": result.error_code,
            "error_message": result.error_message,
            "retryable": result.retryable,
            "idempotency_key": result.idempotency_key,
            "lease_token": result.lease_token,
            "tool_version": result.tool_version,
            "artifact_bundle_hash_sha256": result.artifact_bundle_hash_sha256,
            "artifact_bundle_signature_hmac_sha256": result.artifact_bundle_signature_hmac_sha256,
            "artifact_signature_version": result.artifact_signature_version,
        }
        now = time.time()
        with self._lock:
            conn = self._connect()
            existing_row = conn.execute(
                """
                SELECT payload_json
                FROM byoc_result_payloads
                WHERE job_id = ?
                """,
                (result.job_id,),
            ).fetchone()
            if existing_row is not None:
                existing = self._payload_to_envelope(str(existing_row[0]))
                if str(existing.idempotency_key).strip() != key:
                    should_replace = resolve_result_conflict(
                        existing=existing,
                        incoming=result,
                        strategy=self._conflict_strategy,
                    )
                    if not should_replace:
                        return ByocResultIngestOutcome(
                            accepted=False,
                            duplicate=False,
                            reason_code="BYOC_RESULT_CONFLICT_REJECTED",
                        )
            try:
                conn.execute(
                    """
                    INSERT INTO byoc_result_idempotency (idempotency_key, tenant_id, job_id, created_at_epoch)
                    VALUES (?, ?, ?, ?)
                    """,
                    (key, result.tenant_id, result.job_id, now),
                )
            except sqlite3.IntegrityError:
                return ByocResultIngestOutcome(
                    accepted=True,
                    duplicate=True,
                    reason_code="IDEMPOTENT_DUPLICATE",
                )
            conn.execute(
                """
                INSERT INTO byoc_result_payloads (job_id, tenant_id, payload_json, created_at_epoch)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    tenant_id = excluded.tenant_id,
                    payload_json = excluded.payload_json,
                    created_at_epoch = excluded.created_at_epoch
                """,
                (result.job_id, result.tenant_id, json.dumps(payload), now),
            )
            conn.commit()
            if existing_row is not None:
                return ByocResultIngestOutcome(
                    accepted=True,
                    duplicate=False,
                    reason_code="BYOC_RESULT_CONFLICT_REPLACED",
                )
            return ByocResultIngestOutcome(
                accepted=True,
                duplicate=False,
                reason_code="INGESTED",
            )

    def consume(self, job_id: str) -> ByocToolResultEnvelope | None:
        normalized = str(job_id).strip()
        if not normalized:
            return None
        with self._lock:
            conn = self._connect()
            row = conn.execute(
                """
                SELECT payload_json
                FROM byoc_result_payloads
                WHERE job_id = ?
                """,
                (normalized,),
            ).fetchone()
            if row is None:
                return None
            conn.execute(
                "DELETE FROM byoc_result_payloads WHERE job_id = ?",
                (normalized,),
            )
            conn.commit()
        data = json.loads(str(row[0]))
        return ByocToolResultEnvelope(
            job_id=str(data.get("job_id", "")),
            tenant_id=str(data.get("tenant_id", "")),
            run_id=str(data.get("run_id", "")),
            call_id=str(data.get("call_id", "")),
            tool_name=str(data.get("tool_name", "")),
            status=str(data.get("status", "")),
            output=dict(data.get("output", {}) or {}),
            error_code=str(data.get("error_code", "")),
            error_message=str(data.get("error_message", "")),
            retryable=bool(data.get("retryable", False)),
            idempotency_key=str(data.get("idempotency_key", "")),
            lease_token=str(data.get("lease_token", "")),
            tool_version=str(data.get("tool_version", "")),
            artifact_bundle_hash_sha256=str(data.get("artifact_bundle_hash_sha256", "")),
            artifact_bundle_signature_hmac_sha256=str(data.get("artifact_bundle_signature_hmac_sha256", "")),
            artifact_signature_version=str(data.get("artifact_signature_version", "")),
        )

    def has_idempotency_key(self, key: str) -> bool:
        normalized = str(key).strip()
        if not normalized:
            return False
        with self._lock:
            conn = self._connect()
            row = conn.execute(
                "SELECT 1 FROM byoc_result_idempotency WHERE idempotency_key = ? LIMIT 1",
                (normalized,),
            ).fetchone()
        return row is not None

    def health_metrics(self, *, tenant_id: str) -> dict[str, int]:
        normalized = str(tenant_id).strip()
        if not normalized:
            return {"pending_result_payloads": 0, "idempotency_keys_total": 0}
        with self._lock:
            conn = self._connect()
            row_payloads = conn.execute(
                "SELECT COUNT(1) FROM byoc_result_payloads WHERE tenant_id = ?",
                (normalized,),
            ).fetchone()
            row_idempotency = conn.execute(
                "SELECT COUNT(1) FROM byoc_result_idempotency WHERE tenant_id = ?",
                (normalized,),
            ).fetchone()
        return {
            "pending_result_payloads": int(row_payloads[0]) if row_payloads else 0,
            "idempotency_keys_total": int(row_idempotency[0]) if row_idempotency else 0,
        }

    def cleanup_retention(
        self,
        *,
        tenant_id: str,
        result_ttl_seconds: int,
        idempotency_ttl_seconds: int,
        max_result_records: int,
    ) -> dict[str, int]:
        normalized = str(tenant_id).strip()
        if not normalized:
            return {"result_payloads_pruned": 0, "idempotency_pruned": 0}
        now = time.time()
        result_cutoff = now - max(int(result_ttl_seconds), 1)
        idempotency_cutoff = now - max(int(idempotency_ttl_seconds), 1)
        result_pruned = 0
        idempotency_pruned = 0
        with self._lock:
            conn = self._connect()
            payload_cursor = conn.execute(
                """
                DELETE FROM byoc_result_payloads
                WHERE tenant_id = ? AND created_at_epoch <= ?
                """,
                (normalized, result_cutoff),
            )
            result_pruned += max(int(payload_cursor.rowcount), 0)
            idempotency_cursor = conn.execute(
                """
                DELETE FROM byoc_result_idempotency
                WHERE tenant_id = ? AND created_at_epoch <= ?
                """,
                (normalized, idempotency_cutoff),
            )
            idempotency_pruned += max(int(idempotency_cursor.rowcount), 0)
            overflow_rows = conn.execute(
                """
                SELECT job_id
                FROM byoc_result_payloads
                WHERE tenant_id = ?
                ORDER BY created_at_epoch ASC, rowid ASC
                """,
                (normalized,),
            ).fetchall()
            overflow = max(0, len(overflow_rows) - max(int(max_result_records), 0))
            for row in overflow_rows[:overflow]:
                conn.execute("DELETE FROM byoc_result_payloads WHERE job_id = ?", (str(row[0]),))
                result_pruned += 1
            conn.commit()
        return {"result_payloads_pruned": result_pruned, "idempotency_pruned": idempotency_pruned}

    def _ensure_schema(self) -> None:
        with self._lock:
            conn = self._connect()
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS byoc_result_idempotency (
                    idempotency_key TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL DEFAULT '',
                    job_id TEXT NOT NULL,
                    created_at_epoch REAL NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS byoc_result_payloads (
                    job_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL DEFAULT '',
                    payload_json TEXT NOT NULL,
                    created_at_epoch REAL NOT NULL
                )
                """
            )
            if not self._has_column(conn, "byoc_result_idempotency", "tenant_id"):
                conn.execute("ALTER TABLE byoc_result_idempotency ADD COLUMN tenant_id TEXT NOT NULL DEFAULT ''")
            if not self._has_column(conn, "byoc_result_payloads", "tenant_id"):
                conn.execute("ALTER TABLE byoc_result_payloads ADD COLUMN tenant_id TEXT NOT NULL DEFAULT ''")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_byoc_result_payloads_tenant ON byoc_result_payloads (tenant_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_byoc_result_idempotency_tenant ON byoc_result_idempotency (tenant_id)"
            )
            conn.commit()

    @staticmethod
    def _payload_to_envelope(payload_json: str) -> ByocToolResultEnvelope:
        data = json.loads(payload_json)
        return ByocToolResultEnvelope(
            job_id=str(data.get("job_id", "")),
            tenant_id=str(data.get("tenant_id", "")),
            run_id=str(data.get("run_id", "")),
            call_id=str(data.get("call_id", "")),
            tool_name=str(data.get("tool_name", "")),
            status=str(data.get("status", "")),
            output=dict(data.get("output", {}) or {}),
            error_code=str(data.get("error_code", "")),
            error_message=str(data.get("error_message", "")),
            retryable=bool(data.get("retryable", False)),
            idempotency_key=str(data.get("idempotency_key", "")),
            lease_token=str(data.get("lease_token", "")),
            tool_version=str(data.get("tool_version", "")),
            artifact_bundle_hash_sha256=str(data.get("artifact_bundle_hash_sha256", "")),
            artifact_bundle_signature_hmac_sha256=str(data.get("artifact_bundle_signature_hmac_sha256", "")),
            artifact_signature_version=str(data.get("artifact_signature_version", "")),
        )


class SQLiteReplayGuard(_SQLiteStoreMixin, ReplayGuard):
    """SQLite-backed replay guard for nonce/jti keys with TTL pruning."""

    def __init__(self, db_path: str) -> None:
        super().__init__(db_path)
        self._ensure_schema()

    def mark_once(self, *, key: str, ttl_seconds: int) -> bool:
        normalized = str(key).strip()
        if not normalized:
            return False
        now = time.time()
        ttl = max(int(ttl_seconds), 1)
        with self._lock:
            conn = self._connect()
            conn.execute(
                "DELETE FROM byoc_replay_guard WHERE expires_at_epoch <= ?",
                (now,),
            )
            try:
                conn.execute(
                    """
                    INSERT INTO byoc_replay_guard (guard_key, expires_at_epoch)
                    VALUES (?, ?)
                    """,
                    (normalized, now + ttl),
                )
            except sqlite3.IntegrityError:
                conn.commit()
                return False
            conn.commit()
            return True

    def health_metrics(self, *, tenant_id: str) -> dict[str, int]:
        normalized = str(tenant_id).strip()
        if not normalized:
            return {"replay_keys_active": 0}
        prefix = f"{normalized}:%"
        now = time.time()
        with self._lock:
            conn = self._connect()
            conn.execute(
                "DELETE FROM byoc_replay_guard WHERE expires_at_epoch <= ?",
                (now,),
            )
            row = conn.execute(
                "SELECT COUNT(1) FROM byoc_replay_guard WHERE guard_key LIKE ?",
                (prefix,),
            ).fetchone()
            conn.commit()
        return {"replay_keys_active": int(row[0]) if row else 0}

    def cleanup_retention(self, *, tenant_id: str) -> dict[str, int]:
        normalized = str(tenant_id).strip()
        if not normalized:
            return {"replay_keys_pruned": 0}
        now = time.time()
        prefix = f"{normalized}:%"
        with self._lock:
            conn = self._connect()
            cursor = conn.execute(
                """
                DELETE FROM byoc_replay_guard
                WHERE guard_key LIKE ? AND expires_at_epoch <= ?
                """,
                (prefix, now),
            )
            conn.commit()
        return {"replay_keys_pruned": max(int(cursor.rowcount), 0)}

    def _ensure_schema(self) -> None:
        with self._lock:
            conn = self._connect()
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS byoc_replay_guard (
                    guard_key TEXT PRIMARY KEY,
                    expires_at_epoch REAL NOT NULL
                )
                """
            )
            conn.commit()

