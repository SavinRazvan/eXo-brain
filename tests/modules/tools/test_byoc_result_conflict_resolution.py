"""
File: test_byoc_result_conflict_resolution.py
Path: tests/modules/tools/test_byoc_result_conflict_resolution.py
Role: Validates BYOC result conflict-resolution strategies in memory and sqlite stores.
Used By:
 - pytest
Depends On:
 - src/tools/byoc/result_store.py
 - src/tools/byoc/sqlite_store.py
Notes:
 - Ensures conflicting result submissions are resolved deterministically.
"""

from __future__ import annotations

import time
from pathlib import Path

from src.tools.byoc.job_contracts import ByocResultStatus, ByocToolResultEnvelope
from src.tools.byoc.result_store import (
    ByocResultConflictStrategy,
    ByocResultIngestOutcome,
    ByocResultStore,
    InMemoryByocResultStore,
    InMemoryReplayGuard,
    ReplayGuard,
)
from src.tools.byoc.sqlite_store import SQLiteByocResultStore


def _result(*, job_id: str, idempotency_key: str, status: str, value: int) -> ByocToolResultEnvelope:
    return ByocToolResultEnvelope(
        job_id=job_id,
        tenant_id="t1",
        run_id="run_1",
        call_id="call_1",
        tool_name="echo_tool",
        status=status,
        output={"value": value},
        idempotency_key=idempotency_key,
        lease_token="lease_1",
    )


def test_inmemory_result_store_first_write_wins_rejects_conflict() -> None:
    store = InMemoryByocResultStore(conflict_strategy=ByocResultConflictStrategy.FIRST_WRITE_WINS)
    first = store.ingest(_result(job_id="job_a", idempotency_key="t1:1", status=ByocResultStatus.ERROR, value=1))
    second = store.ingest(_result(job_id="job_a", idempotency_key="t1:2", status=ByocResultStatus.SUCCESS, value=9))
    assert first.accepted is True
    assert second.accepted is False
    assert second.reason_code == "BYOC_RESULT_CONFLICT_REJECTED"
    consumed = store.consume("job_a")
    assert consumed is not None
    assert consumed.output["value"] == 1
    conflict_counts = store.list_conflict_counts(tenant_id="t1")
    assert len(conflict_counts) == 1
    assert conflict_counts[0].strategy == "first_write_wins"
    assert conflict_counts[0].reason_code == "BYOC_RESULT_CONFLICT_REJECTED"
    assert conflict_counts[0].tool_name == "echo_tool"
    assert conflict_counts[0].tool_version == ""
    assert conflict_counts[0].count == 1


def test_inmemory_result_store_last_write_wins_replaces_conflict() -> None:
    store = InMemoryByocResultStore(conflict_strategy=ByocResultConflictStrategy.LAST_WRITE_WINS)
    first = store.ingest(_result(job_id="job_b", idempotency_key="t1:1", status=ByocResultStatus.ERROR, value=1))
    second = store.ingest(_result(job_id="job_b", idempotency_key="t1:2", status=ByocResultStatus.SUCCESS, value=9))
    assert first.accepted is True
    assert second.accepted is True
    assert second.reason_code == "BYOC_RESULT_CONFLICT_REPLACED"
    consumed = store.consume("job_b")
    assert consumed is not None
    assert consumed.output["value"] == 9
    conflict_counts = store.list_conflict_counts(tenant_id="t1")
    assert len(conflict_counts) == 1
    assert conflict_counts[0].strategy == "last_write_wins"
    assert conflict_counts[0].reason_code == "BYOC_RESULT_CONFLICT_REPLACED"
    assert conflict_counts[0].count == 1


def test_inmemory_result_store_prefer_success_promotes_success_result() -> None:
    store = InMemoryByocResultStore(conflict_strategy=ByocResultConflictStrategy.PREFER_SUCCESS)
    first = store.ingest(_result(job_id="job_c", idempotency_key="t1:1", status=ByocResultStatus.ERROR, value=1))
    second = store.ingest(_result(job_id="job_c", idempotency_key="t1:2", status=ByocResultStatus.SUCCESS, value=9))
    third = store.ingest(_result(job_id="job_c", idempotency_key="t1:3", status=ByocResultStatus.ERROR, value=4))
    assert first.accepted is True
    assert second.accepted is True
    assert second.reason_code == "BYOC_RESULT_CONFLICT_REPLACED"
    assert third.accepted is False
    assert third.reason_code == "BYOC_RESULT_CONFLICT_REJECTED"
    consumed = store.consume("job_c")
    assert consumed is not None
    assert consumed.status == ByocResultStatus.SUCCESS
    conflict_counts = store.list_conflict_counts(tenant_id="t1")
    reasons = {item.reason_code: item.count for item in conflict_counts}
    assert reasons["BYOC_RESULT_CONFLICT_REPLACED"] == 1
    assert reasons["BYOC_RESULT_CONFLICT_REJECTED"] == 1


def test_sqlite_result_store_applies_conflict_strategy_replace(tmp_path: Path) -> None:
    db_path = tmp_path / "byoc_conflict.sqlite"
    store = SQLiteByocResultStore(
        str(db_path),
        conflict_strategy=ByocResultConflictStrategy.LAST_WRITE_WINS,
    )
    first = store.ingest(_result(job_id="job_d", idempotency_key="t1:1", status=ByocResultStatus.ERROR, value=1))
    second = store.ingest(_result(job_id="job_d", idempotency_key="t1:2", status=ByocResultStatus.SUCCESS, value=9))
    assert first.accepted is True
    assert second.accepted is True
    assert second.reason_code == "BYOC_RESULT_CONFLICT_REPLACED"
    consumed = store.consume("job_d")
    assert consumed is not None
    assert consumed.output["value"] == 9
    conflict_counts = store.list_conflict_counts(tenant_id="t1")
    assert len(conflict_counts) == 1
    assert conflict_counts[0].strategy == "last_write_wins"
    assert conflict_counts[0].reason_code == "BYOC_RESULT_CONFLICT_REPLACED"
    assert conflict_counts[0].count == 1


def test_inmemory_prefer_success_keeps_existing_success_when_new_success_arrives() -> None:
    store = InMemoryByocResultStore(conflict_strategy=ByocResultConflictStrategy.PREFER_SUCCESS)
    first = store.ingest(_result(job_id="job_e", idempotency_key="t1:e1", status=ByocResultStatus.SUCCESS, value=11))
    second = store.ingest(_result(job_id="job_e", idempotency_key="t1:e2", status=ByocResultStatus.SUCCESS, value=22))
    assert first.accepted is True
    assert second.accepted is False
    assert second.reason_code == "BYOC_RESULT_CONFLICT_REJECTED"
    consumed = store.consume("job_e")
    assert consumed is not None
    assert consumed.output["value"] == 11


class _MinimalResultStore(ByocResultStore):
    def ingest(self, result: ByocToolResultEnvelope) -> ByocResultIngestOutcome:
        return ByocResultIngestOutcome(accepted=True, duplicate=False, reason_code="noop")

    def consume(self, job_id: str) -> ByocToolResultEnvelope | None:
        return None


def test_byoc_result_store_default_hooks_return_safe_defaults() -> None:
    store = _MinimalResultStore()
    assert store.has_idempotency_key("any") is False
    assert store.conflict_strategy_name() == "unknown"
    assert store.list_conflict_counts(tenant_id="t") == []


class _MinimalReplayGuard(ReplayGuard):
    def mark_once(self, *, key: str, ttl_seconds: int) -> bool:
        return True


def test_replay_guard_default_metrics_and_cleanup() -> None:
    guard = _MinimalReplayGuard()
    assert guard.health_metrics(tenant_id="t") == {"replay_keys_active": 0}
    assert guard.cleanup_retention(tenant_id="t") == {"replay_keys_pruned": 0}


def test_inmemory_result_store_rejects_blank_idempotency_key() -> None:
    store = InMemoryByocResultStore()
    outcome = store.ingest(_result(job_id="j", idempotency_key="  ", status=ByocResultStatus.SUCCESS, value=1))
    assert outcome.accepted is False
    assert outcome.reason_code == "IDEMPOTENCY_KEY_REQUIRED"


def test_inmemory_result_store_duplicate_idempotency_short_circuits() -> None:
    store = InMemoryByocResultStore()
    payload = _result(job_id="j1", idempotency_key="t1:same", status=ByocResultStatus.SUCCESS, value=1)
    first = store.ingest(payload)
    second = store.ingest(payload)
    assert first.reason_code == "INGESTED"
    assert second.duplicate is True
    assert second.reason_code == "IDEMPOTENT_DUPLICATE"


def test_inmemory_consume_and_has_idempotency_blank_keys() -> None:
    store = InMemoryByocResultStore()
    assert store.consume("  ") is None
    assert store.has_idempotency_key(" ") is False


def test_inmemory_list_conflict_counts_blank_tenant_returns_empty() -> None:
    store = InMemoryByocResultStore()
    assert store.list_conflict_counts(tenant_id="   ") == []


def test_inmemory_replay_guard_blank_key_rejected() -> None:
    guard = InMemoryReplayGuard()
    assert guard.mark_once(key="  ", ttl_seconds=10) is False


def test_inmemory_replay_guard_health_and_cleanup_retention() -> None:
    guard = InMemoryReplayGuard()
    assert guard.mark_once(key="t1:n1", ttl_seconds=1) is True
    assert guard.mark_once(key="t1:n1", ttl_seconds=1) is False
    metrics = guard.health_metrics(tenant_id="t1")
    assert metrics["replay_keys_active"] == 1
    pruned = guard.cleanup_retention(tenant_id="t1")
    assert pruned["replay_keys_pruned"] >= 0


def test_inmemory_list_conflict_counts_skips_other_tenants() -> None:
    store = InMemoryByocResultStore()
    store._conflict_counts[("t_other", "R", "x@y")] = 1  # type: ignore[attr-defined]
    store._conflict_counts[("t1", "R", "x@y")] = 2  # type: ignore[attr-defined]
    rows = store.list_conflict_counts(tenant_id="t1")
    assert len(rows) == 1
    assert rows[0].count == 2


def test_inmemory_replay_guard_cleanup_unlocked_pops_stale_keys() -> None:
    guard = InMemoryReplayGuard()
    past = time.time() - 10.0
    guard._expires_at_epoch["t1:k1"] = past  # type: ignore[attr-defined]
    guard._cleanup_unlocked(time.time())
    assert "t1:k1" not in guard._expires_at_epoch


def test_inmemory_conflict_list_tool_key_without_at_separator() -> None:
    store = InMemoryByocResultStore()
    store._conflict_counts[("t1", "BYOC_RESULT_CONFLICT_REJECTED", "baretool")] = 2  # type: ignore[attr-defined]
    rows = store.list_conflict_counts(tenant_id="t1")
    assert len(rows) == 1
    assert rows[0].tool_name == "baretool"
    assert rows[0].tool_version == ""
