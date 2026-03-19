"""
File: test_byoc_sqlite_store_branches.py
Path: tests/modules/tools/test_byoc_sqlite_store_branches.py
Role: Branch-focused tests for SQLite BYOC stores and migration/retention edge behavior.
Used By:
 - pytest
Depends On:
 - src/tools/byoc/sqlite_store.py
 - src/tools/byoc/job_contracts.py
 - src/tools/byoc/result_store.py
Notes:
 - Exercises SQLite-specific branches not covered by connector-level integration tests.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from src.tools.byoc.job_contracts import ByocResultStatus, ByocToolJobEnvelope, ByocToolResultEnvelope
from src.tools.byoc.result_store import ByocResultConflictStrategy
from src.tools.byoc.sqlite_store import (
    SQLiteByocJobQueueStore,
    SQLiteByocResultStore,
    SQLiteReplayGuard,
)


def _job(job_id: str, *, tenant_id: str = "t1", call_id: str | None = None) -> ByocToolJobEnvelope:
    return ByocToolJobEnvelope(
        job_id=job_id,
        tenant_id=tenant_id,
        run_id=f"run_{job_id}",
        call_id=call_id or f"call_{job_id}",
        tool_name="echo_tool",
        arguments={"value": 1},
        timeout_ms=500,
        correlation_id=f"corr_{job_id}",
        idempotency_key=f"idem_{job_id}",
        tool_version="1.0.0",
        package_ref="pkg://echo/1.0.0",
        entry_file="handler.py",
        entrypoint="run",
    )


def _result(job_id: str, *, idempotency_key: str, status: str = ByocResultStatus.SUCCESS) -> ByocToolResultEnvelope:
    return ByocToolResultEnvelope(
        job_id=job_id,
        tenant_id="t1",
        run_id=f"run_{job_id}",
        call_id=f"call_{job_id}",
        tool_name="echo_tool",
        status=status,
        output={"value": 1},
        idempotency_key=idempotency_key,
        lease_token=f"lease_{job_id}",
        tool_version="1.0.0",
    )


def test_sqlite_job_store_shared_memory_connection_and_false_paths() -> None:
    store = SQLiteByocJobQueueStore(":memory:")
    conn_a = store._connect()  # noqa: SLF001
    conn_b = store._connect()  # noqa: SLF001
    assert conn_a is conn_b

    assert store.complete_claim(job_id="missing", lease_token="x") is False
    assert store.dead_letter_count(tenant_id="") == 0
    assert store.list_dead_letter_jobs(tenant_id="", limit=10) == []
    assert store.health_metrics(tenant_id="") == {
        "queued_jobs": 0,
        "leased_jobs": 0,
        "completed_jobs": 0,
        "cancelled_jobs": 0,
    }
    assert store.cleanup_retention(
        tenant_id="",
        completed_ttl_seconds=1,
        cancelled_ttl_seconds=1,
        max_completed_records=0,
        max_cancelled_records=0,
    ) == {"completed_pruned": 0, "cancelled_pruned": 0}


def test_sqlite_job_store_expired_complete_and_dead_letter_requeue_paths(tmp_path: Path) -> None:
    store = SQLiteByocJobQueueStore(str(tmp_path / "jobs.db"))
    store.enqueue(_job("j1"))
    claim = store.claim_next(tenant_id="t1", worker_id="w1", lease_ttl_seconds=1)
    assert claim is not None
    time.sleep(1.1)
    assert store.complete_claim(job_id="j1", lease_token=claim.job.lease_token) is False
    # Already requeued by expired complete_claim branch; reclaim and force DLQ on next expiry.
    claim2 = store.claim_next(tenant_id="t1", worker_id="w2", lease_ttl_seconds=1)
    assert claim2 is not None
    time.sleep(1.1)
    assert store.requeue_expired_leases(max_claim_attempts_before_dlq=2) >= 0
    assert store.dead_letter_count(tenant_id="t1") == 1

    rows = store.list_dead_letter_jobs(tenant_id="t1", limit=10)
    assert len(rows) == 1
    assert rows[0]["dead_letter_reason_code"] == "BYOC_LEASE_RETRY_EXHAUSTED"
    assert store.replay_dead_letter_job(tenant_id="", job_id="j1") is False
    assert store.replay_dead_letter_job(tenant_id="t2", job_id="j1") is False
    assert store.replay_dead_letter_job(tenant_id="t1", job_id="missing") is False
    assert store.replay_dead_letter_job(tenant_id="t1", job_id="j1") is True


def test_sqlite_job_store_additional_false_branches(tmp_path: Path) -> None:
    store = SQLiteByocJobQueueStore(str(tmp_path / "jobs_false.db"))
    store.enqueue(_job("j1"))
    assert store.cancel_pending_call(call_id=" ") == 0
    # status != leased branch for complete_claim
    assert store.complete_claim(job_id="j1", lease_token="wrong_token") is False
    claim = store.claim_next(tenant_id="t1", worker_id="w1", lease_ttl_seconds=1)
    assert claim is not None

    # token mismatch branch for complete_claim
    assert store.complete_claim(job_id="j1", lease_token="wrong_token") is False

    # get_leased_job false branches
    assert store.get_leased_job(job_id="missing", lease_token="x") is None
    assert store.get_leased_job(job_id="j1", lease_token="wrong") is None
    time.sleep(1.1)
    assert store.get_leased_job(job_id="j1", lease_token=claim.job.lease_token) is None
    claim2 = store.claim_next(tenant_id="t1", worker_id="w2", lease_ttl_seconds=30)
    assert claim2 is not None
    assert store.complete_claim(job_id="j1", lease_token=claim2.job.lease_token) is True
    store.complete_claim(job_id="j1", lease_token=claim.job.lease_token)
    assert store.get_leased_job(job_id="j1", lease_token=claim.job.lease_token) is None

    # replay_dead_letter_job normalized empty job path
    assert store.replay_dead_letter_job(tenant_id="t1", job_id="") is False


def test_sqlite_job_store_cleanup_overflow_branch(tmp_path: Path) -> None:
    store = SQLiteByocJobQueueStore(str(tmp_path / "jobs_cleanup_overflow.db"))
    now = time.time()
    for idx in range(3):
        store.enqueue(_job(f"c{idx}", tenant_id="tenant"))
    for idx in range(2):
        store.enqueue(_job(f"x{idx}", tenant_id="tenant"))
    conn = store._connect()  # noqa: SLF001
    for idx in range(3):
        conn.execute(
            "UPDATE byoc_jobs SET status='completed', completed_at_epoch=? WHERE job_id=?",
            (now + idx + 1000, f"c{idx}"),
        )
    for idx in range(2):
        conn.execute(
            "UPDATE byoc_jobs SET status='cancelled', cancelled_at_epoch=? WHERE job_id=?",
            (now + idx + 1000, f"x{idx}"),
        )
    conn.commit()
    out = store.cleanup_retention(
        tenant_id="tenant",
        completed_ttl_seconds=99999,
        cancelled_ttl_seconds=99999,
        max_completed_records=1,
        max_cancelled_records=1,
    )
    assert out["completed_pruned"] == 2
    assert out["cancelled_pruned"] == 1


def test_sqlite_job_store_migration_columns_are_added(tmp_path: Path) -> None:
    db_path = tmp_path / "jobs_migration.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE byoc_jobs (
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
            claim_attempt INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    conn.commit()
    conn.close()

    store = SQLiteByocJobQueueStore(str(db_path))
    conn2 = store._connect()  # noqa: SLF001
    columns = {str(row[1]) for row in conn2.execute("PRAGMA table_info(byoc_jobs)").fetchall()}
    assert "completed_at_epoch" in columns
    assert "cancelled_at_epoch" in columns
    assert "dead_lettered_at_epoch" in columns
    assert "artifact_signature_version" in columns


def test_sqlite_result_store_branch_paths_and_retention(tmp_path: Path) -> None:
    store = SQLiteByocResultStore(str(tmp_path / "results.db"))

    missing_key = store.ingest(_result("j_missing_key", idempotency_key=""))
    assert missing_key.accepted is False
    assert missing_key.reason_code == "IDEMPOTENCY_KEY_REQUIRED"

    first = store.ingest(_result("j1", idempotency_key="k1", status=ByocResultStatus.ERROR))
    assert first.accepted is True
    duplicate = store.ingest(_result("j2", idempotency_key="k1"))
    assert duplicate.accepted is True
    assert duplicate.duplicate is True

    reject_store = SQLiteByocResultStore(
        str(tmp_path / "results_reject.db"),
        conflict_strategy=ByocResultConflictStrategy.FIRST_WRITE_WINS,
    )
    assert reject_store.ingest(_result("job_a", idempotency_key="id_a")).accepted is True
    rejected = reject_store.ingest(_result("job_a", idempotency_key="id_b", status=ByocResultStatus.ERROR))
    assert rejected.accepted is False
    assert rejected.reason_code == "BYOC_RESULT_CONFLICT_REJECTED"

    replace_store = SQLiteByocResultStore(
        str(tmp_path / "results_replace.db"),
        conflict_strategy=ByocResultConflictStrategy.LAST_WRITE_WINS,
    )
    assert replace_store.ingest(_result("job_b", idempotency_key="id_1", status=ByocResultStatus.ERROR)).accepted is True
    replaced = replace_store.ingest(_result("job_b", idempotency_key="id_2", status=ByocResultStatus.SUCCESS))
    assert replaced.accepted is True
    assert replaced.reason_code == "BYOC_RESULT_CONFLICT_REPLACED"
    consumed = replace_store.consume("job_b")
    assert consumed is not None
    assert consumed.status == ByocResultStatus.SUCCESS
    assert replace_store.consume("") is None
    assert replace_store.consume("job_b") is None

    assert replace_store.has_idempotency_key("") is False
    assert replace_store.health_metrics(tenant_id="") == {
        "pending_result_payloads": 0,
        "idempotency_keys_total": 0,
    }
    assert replace_store.cleanup_retention(
        tenant_id="",
        result_ttl_seconds=1,
        idempotency_ttl_seconds=1,
        max_result_records=0,
    ) == {"result_payloads_pruned": 0, "idempotency_pruned": 0}
    assert replace_store.list_conflict_counts(tenant_id="") == []
    assert replace_store.conflict_strategy_name() == ByocResultConflictStrategy.LAST_WRITE_WINS.value
    metrics = replace_store.health_metrics(tenant_id="t1")
    assert metrics["pending_result_payloads"] >= 0
    assert metrics["idempotency_keys_total"] >= 0

    # overflow prune branch
    for idx in range(3):
        replace_store.ingest(_result(f"overflow_{idx}", idempotency_key=f"ov_{idx}"))
    cleanup = replace_store.cleanup_retention(
        tenant_id="t1",
        result_ttl_seconds=99999,
        idempotency_ttl_seconds=99999,
        max_result_records=1,
    )
    assert cleanup["result_payloads_pruned"] >= 2


def test_sqlite_result_store_migration_columns_and_conflict_record_commit(tmp_path: Path) -> None:
    db_path = tmp_path / "results_migration.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE byoc_result_idempotency (
            idempotency_key TEXT PRIMARY KEY,
            job_id TEXT NOT NULL,
            created_at_epoch REAL NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE byoc_result_payloads (
            job_id TEXT PRIMARY KEY,
            payload_json TEXT NOT NULL,
            created_at_epoch REAL NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()

    store = SQLiteByocResultStore(str(db_path))
    conn2 = store._connect()  # noqa: SLF001
    id_cols = {str(row[1]) for row in conn2.execute("PRAGMA table_info(byoc_result_idempotency)").fetchall()}
    payload_cols = {str(row[1]) for row in conn2.execute("PRAGMA table_info(byoc_result_payloads)").fetchall()}
    assert "tenant_id" in id_cols
    assert "tenant_id" in payload_cols

    # trigger _record_conflict path without externally supplied connection
    store._record_conflict(  # noqa: SLF001
        tenant_id="",
        tool_name="",
        tool_version="",
        reason_code="",
        conn=None,
    )
    rows = store.list_conflict_counts(tenant_id="default")
    assert len(rows) == 1


def test_sqlite_replay_guard_branch_paths(tmp_path: Path) -> None:
    guard = SQLiteReplayGuard(str(tmp_path / "replay.db"))
    assert guard.mark_once(key="", ttl_seconds=1) is False
    assert guard.mark_once(key="t1:nonce:1", ttl_seconds=1) is True
    assert guard.mark_once(key="t1:nonce:1", ttl_seconds=1) is False
    assert guard.health_metrics(tenant_id="") == {"replay_keys_active": 0}
    assert guard.cleanup_retention(tenant_id="") == {"replay_keys_pruned": 0}
    time.sleep(1.1)
    cleanup = guard.cleanup_retention(tenant_id="t1")
    assert cleanup["replay_keys_pruned"] >= 1
    metrics = guard.health_metrics(tenant_id="t1")
    assert metrics["replay_keys_active"] == 0
