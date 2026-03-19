"""
File: test_byoc_job_store.py
Path: tests/modules/tools/test_byoc_job_store.py
Role: Unit tests for in-memory BYOC queue/lease/dead-letter lifecycle behavior.
Used By:
 - pytest
Depends On:
 - src/tools/byoc/job_store.py
 - src/tools/byoc/job_contracts.py
Notes:
 - Covers lease expiry, cancellation, replay, metrics, and retention cleanup branches.
"""

from __future__ import annotations

from collections import deque
import time

from src.tools.byoc.job_contracts import ByocToolJobEnvelope
from src.tools.byoc.job_store import ByocJobQueueStore, InMemoryByocJobQueueStore


def _job(
    job_id: str,
    *,
    tenant_id: str = "t1",
    call_id: str | None = None,
    tool_name: str = "compute",
) -> ByocToolJobEnvelope:
    return ByocToolJobEnvelope(
        job_id=job_id,
        tenant_id=tenant_id,
        run_id=f"run_{job_id}",
        call_id=call_id or f"call_{job_id}",
        tool_name=tool_name,
        arguments={"x": 1},
        timeout_ms=1000,
        idempotency_key=f"idem_{job_id}",
    )


def test_enqueue_duplicate_claim_complete_and_invalid_complete_paths() -> None:
    store = InMemoryByocJobQueueStore()
    j1 = _job("j1")
    store.enqueue(j1)
    store.enqueue(j1)  # duplicate id no-op branch
    assert store.queue_depth() == 1

    claim = store.claim_next(tenant_id="t1", worker_id="w1", lease_ttl_seconds=30)
    assert claim is not None
    assert claim.job.job_id == "j1"
    assert claim.job.claim_attempt == 1

    assert store.complete_claim(job_id="missing", lease_token="x") is False
    assert store.complete_claim(job_id="j1", lease_token="wrong") is False
    assert store.complete_claim(job_id="j1", lease_token=claim.job.lease_token) is True
    # Already completed, no longer leased.
    assert store.complete_claim(job_id="j1", lease_token=claim.job.lease_token) is False


def test_get_leased_job_validates_token_and_expiry() -> None:
    store = InMemoryByocJobQueueStore()
    store.enqueue(_job("j1"))
    claim = store.claim_next(tenant_id="t1", worker_id="w1", lease_ttl_seconds=1)
    assert claim is not None

    assert store.get_leased_job(job_id="j1", lease_token="wrong") is None
    assert store.get_leased_job(job_id="j1", lease_token=claim.job.lease_token) is not None
    time.sleep(1.1)
    assert store.get_leased_job(job_id="j1", lease_token=claim.job.lease_token) is None


def test_complete_claim_rejects_expired_lease() -> None:
    store = InMemoryByocJobQueueStore()
    store.enqueue(_job("j1"))
    claim = store.claim_next(tenant_id="t1", worker_id="w1", lease_ttl_seconds=1)
    assert claim is not None
    time.sleep(1.1)
    assert store.complete_claim(job_id="j1", lease_token=claim.job.lease_token) is False


def test_get_leased_job_returns_none_when_not_leased() -> None:
    store = InMemoryByocJobQueueStore()
    store.enqueue(_job("j1"))
    claim = store.claim_next(tenant_id="t1", worker_id="w1", lease_ttl_seconds=30)
    assert claim is not None
    assert store.complete_claim(job_id="j1", lease_token=claim.job.lease_token) is True
    assert store.get_leased_job(job_id="j1", lease_token=claim.job.lease_token) is None


def test_claim_next_requeues_expired_and_can_dead_letter() -> None:
    store = InMemoryByocJobQueueStore()
    store.enqueue(_job("j1"))
    first = store.claim_next(tenant_id="t1", worker_id="w1", lease_ttl_seconds=1)
    assert first is not None
    time.sleep(1.1)
    requeued = store.requeue_expired_leases(max_claim_attempts_before_dlq=3)
    assert requeued == 1
    second = store.claim_next(tenant_id="t1", worker_id="w2", lease_ttl_seconds=1)
    assert second is not None
    assert second.job.claim_attempt == 2

    # Exhaust retries to DLQ.
    time.sleep(1.1)
    assert store.requeue_expired_leases(max_claim_attempts_before_dlq=2) == 0
    assert store.dead_letter_count(tenant_id="t1") == 1


def test_dead_letter_listing_and_replay() -> None:
    store = InMemoryByocJobQueueStore()
    store.enqueue(_job("j1"))
    claim = store.claim_next(tenant_id="t1", worker_id="w1", lease_ttl_seconds=1)
    assert claim is not None
    time.sleep(1.1)
    store.requeue_expired_leases(max_claim_attempts_before_dlq=1)

    rows = store.list_dead_letter_jobs(tenant_id="t1", limit=5)
    assert len(rows) == 1
    assert rows[0]["job_id"] == "j1"
    assert rows[0]["dead_letter_reason_code"] == "BYOC_LEASE_RETRY_EXHAUSTED"

    assert store.replay_dead_letter_job(tenant_id="", job_id="j1") is False
    assert store.replay_dead_letter_job(tenant_id="t1", job_id="missing") is False
    assert store.replay_dead_letter_job(tenant_id="other", job_id="j1") is False
    assert store.replay_dead_letter_job(tenant_id="t1", job_id="j1") is True
    assert store.dead_letter_count(tenant_id="t1") == 0
    assert store.queue_depth() == 1


def test_claim_next_skips_non_queued_entries_and_returns_none_when_exhausted() -> None:
    store = InMemoryByocJobQueueStore()
    store.enqueue(_job("j1"))
    claim = store.claim_next(tenant_id="t1", worker_id="w1", lease_ttl_seconds=30)
    assert claim is not None
    # Push leased job id back into queue to exercise "state.status != queued" skip branch.
    store._tenant_queue.setdefault("t1", deque()).append("j1")  # noqa: SLF001
    assert store.claim_next(tenant_id="t1", worker_id="w2", lease_ttl_seconds=30) is None


def test_cancel_pending_call_cancels_queued_and_expires_leased() -> None:
    store = InMemoryByocJobQueueStore()
    store.enqueue(_job("j1", call_id="call_x"))
    store.enqueue(_job("j2", call_id="call_x"))
    store.enqueue(_job("j3", call_id="call_other"))

    # Lease one call_x job so cancel path expires lease and requeues then marks cancelled.
    leased = store.claim_next(tenant_id="t1", worker_id="w1", lease_ttl_seconds=30)
    assert leased is not None

    assert store.cancel_pending_call(call_id="") == 0
    affected = store.cancel_pending_call(call_id="call_x")
    assert affected >= 1
    metrics = store.health_metrics(tenant_id="t1")
    assert metrics["cancelled_jobs"] >= 1


def test_health_metrics_and_cleanup_retention() -> None:
    store = InMemoryByocJobQueueStore()
    now = time.time()

    # Seed all lifecycle statuses explicitly for deterministic metrics checks.
    store.enqueue(_job("q1", tenant_id="tenant"))
    store.enqueue(_job("l1", tenant_id="tenant"))
    store.enqueue(_job("c1", tenant_id="tenant"))
    store.enqueue(_job("x1", tenant_id="tenant"))
    store.enqueue(_job("d1", tenant_id="tenant"))
    store.enqueue(_job("other1", tenant_id="other"))
    store._states["l1"].status = "leased"  # noqa: SLF001
    store._states["l1"].lease_token = "lease_l1"  # noqa: SLF001
    store._states["l1"].lease_expires_at_epoch = now + 60  # noqa: SLF001
    store._states["c1"].status = "completed"  # noqa: SLF001
    store._states["c1"].completed_at_epoch = now - 100  # noqa: SLF001
    store._states["x1"].status = "cancelled"  # noqa: SLF001
    store._states["x1"].cancelled_at_epoch = now - 100  # noqa: SLF001
    store._states["d1"].status = "dead_lettered"  # noqa: SLF001
    store._states["d1"].dead_lettered_at_epoch = now - 10  # noqa: SLF001
    store._states["d1"].dead_letter_reason_code = "BYOC_LEASE_RETRY_EXHAUSTED"  # noqa: SLF001

    metrics = store.health_metrics(tenant_id="tenant")
    assert metrics["queued_jobs"] >= 1
    assert metrics["leased_jobs"] >= 1
    assert metrics["completed_jobs"] >= 1
    assert metrics["cancelled_jobs"] >= 1
    assert metrics["dead_lettered_jobs"] >= 1

    result = store.cleanup_retention(
        tenant_id="tenant",
        completed_ttl_seconds=1,
        cancelled_ttl_seconds=1,
        max_completed_records=0,
        max_cancelled_records=0,
    )
    assert result["completed_pruned"] >= 1
    assert result["cancelled_pruned"] >= 1

    empty = store.cleanup_retention(
        tenant_id="",
        completed_ttl_seconds=1,
        cancelled_ttl_seconds=1,
        max_completed_records=0,
        max_cancelled_records=0,
    )
    assert empty == {"completed_pruned": 0, "cancelled_pruned": 0}


def test_cleanup_retention_overflow_prunes_oldest_records() -> None:
    store = InMemoryByocJobQueueStore()
    now = time.time()
    for idx in range(3):
        store.enqueue(_job(f"c{idx}", tenant_id="tenant"))
        store._states[f"c{idx}"].status = "completed"  # noqa: SLF001
        store._states[f"c{idx}"].completed_at_epoch = now + idx  # noqa: SLF001
    for idx in range(2):
        store.enqueue(_job(f"x{idx}", tenant_id="tenant"))
        store._states[f"x{idx}"].status = "cancelled"  # noqa: SLF001
        store._states[f"x{idx}"].cancelled_at_epoch = now + idx  # noqa: SLF001

    result = store.cleanup_retention(
        tenant_id="tenant",
        completed_ttl_seconds=99999,
        cancelled_ttl_seconds=99999,
        max_completed_records=1,
        max_cancelled_records=1,
    )
    assert result["completed_pruned"] == 2
    assert result["cancelled_pruned"] == 1


def test_base_job_store_default_metrics_and_cleanup() -> None:
    class _MinimalStore(ByocJobQueueStore):
        def enqueue(self, job: ByocToolJobEnvelope) -> None:
            _ = job

        def claim_next(self, *, tenant_id: str, worker_id: str, lease_ttl_seconds: int):
            _ = (tenant_id, worker_id, lease_ttl_seconds)
            return None

        def complete_claim(self, *, job_id: str, lease_token: str) -> bool:
            _ = (job_id, lease_token)
            return False

        def get_leased_job(self, *, job_id: str, lease_token: str):
            _ = (job_id, lease_token)
            return None

        def requeue_expired_leases(self, *, max_claim_attempts_before_dlq: int | None = None) -> int:
            _ = max_claim_attempts_before_dlq
            return 0

        def dead_letter_count(self, *, tenant_id: str) -> int:
            _ = tenant_id
            return 0

        def list_dead_letter_jobs(self, *, tenant_id: str, limit: int = 100) -> list[dict[str, str]]:
            _ = (tenant_id, limit)
            return []

        def replay_dead_letter_job(self, *, tenant_id: str, job_id: str) -> bool:
            _ = (tenant_id, job_id)
            return False

        def cancel_pending_call(self, *, call_id: str) -> int:
            _ = call_id
            return 0

        def queue_depth(self) -> int:
            return 1

    store = _MinimalStore()
    assert store.health_metrics(tenant_id="tenant") == {"queued_jobs": 1}
    assert store.cleanup_retention(
        tenant_id="tenant",
        completed_ttl_seconds=10,
        cancelled_ttl_seconds=10,
        max_completed_records=10,
        max_cancelled_records=10,
    ) == {"completed_pruned": 0, "cancelled_pruned": 0}
