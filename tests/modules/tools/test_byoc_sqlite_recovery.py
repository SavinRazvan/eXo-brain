"""
File: test_byoc_sqlite_recovery.py
Path: tests/modules/tools/test_byoc_sqlite_recovery.py
Role: Verify SQLite-backed BYOC stores and restart-recovery behavior.
Used By:
 - pytest
Depends On:
 - src/tools/byoc/sqlite_store.py
 - src/tools/byoc/connector_runtime.py
Notes:
 - Tests durable queue/lease/result/replay behavior across new store/runtime instances.
"""

from __future__ import annotations

import threading
import time

from src.schemas.tool_io import ToolCallContext, ToolStatus
from src.tools.byoc.connector_runtime import TenantByocConnectorRuntime
from src.tools.byoc.job_contracts import ByocResultStatus, ByocToolJobEnvelope, ByocToolResultEnvelope
from src.tools.byoc.sqlite_store import SQLiteByocJobQueueStore, SQLiteByocResultStore, SQLiteReplayGuard
from src.tools.registry import ToolDescriptor


def _call() -> ToolCallContext:
    return ToolCallContext(
        schema_version="1.0",
        call_id="call_sqlite_1",
        session_id="sess_sqlite_1",
        run_id="run_sqlite_1",
        job_id="job_sqlite_1",
        task_id="task_sqlite_1",
        agent_id="agent_sqlite_1",
        provider_id="openai-test",
        tool_name="echo_tool",
        arguments={"value": 55},
        tenant_id="t1",
    )


def _descriptor() -> ToolDescriptor:
    return ToolDescriptor(name="echo_tool", handler=lambda value: value, timeout_ms=3000)


def _wait_claim(runtime: TenantByocConnectorRuntime, token: str, prefix: str) -> dict[str, object] | None:
    deadline = time.time() + 2.0
    attempt = 0
    while time.time() < deadline:
        attempt += 1
        claimed = runtime.claim_next_job(
            tenant_id="t1",
            worker_token=token,
            request_nonce=f"{prefix}-{attempt}",
        )
        if claimed is not None:
            return claimed
        time.sleep(0.02)
    return None


def test_sqlite_job_store_requeues_expired_lease(tmp_path) -> None:
    db_path = str(tmp_path / "byoc_requeue.db")
    store = SQLiteByocJobQueueStore(db_path)
    store.enqueue(
        ByocToolJobEnvelope(
            job_id="job_rq_1",
            tenant_id="t1",
            run_id="run_rq_1",
            call_id="call_rq_1",
            tool_name="echo_tool",
            arguments={"x": 1},
            timeout_ms=1000,
            correlation_id="corr_rq_1",
            idempotency_key="idem_rq_1",
        )
    )
    first = store.claim_next(tenant_id="t1", worker_id="worker-1", lease_ttl_seconds=1)
    assert first is not None
    time.sleep(1.2)
    requeued = store.requeue_expired_leases()
    assert requeued >= 1
    second = store.claim_next(tenant_id="t1", worker_id="worker-2", lease_ttl_seconds=1)
    assert second is not None
    assert second.job.job_id == "job_rq_1"
    assert second.job.claim_attempt >= 2


def test_sqlite_replay_guard_survives_restart_window(tmp_path) -> None:
    db_path = str(tmp_path / "byoc_replay.db")
    guard_a = SQLiteReplayGuard(db_path)
    guard_b = SQLiteReplayGuard(db_path)
    assert guard_a.mark_once(key="tenant:t1:nonce:abc", ttl_seconds=5) is True
    assert guard_b.mark_once(key="tenant:t1:nonce:abc", ttl_seconds=5) is False


def test_byoc_runtime_sqlite_restart_recovery(tmp_path) -> None:
    db_path = str(tmp_path / "byoc_runtime_recovery.db")

    runtime_a = TenantByocConnectorRuntime(
        worker_jwt_secret="test-secret",
        job_store=SQLiteByocJobQueueStore(db_path),
        result_store=SQLiteByocResultStore(db_path),
        replay_guard=SQLiteReplayGuard(db_path),
        lease_ttl_seconds=2,
    )
    call = _call()
    descriptor = _descriptor()
    result_holder: dict[str, object] = {}

    def _execute() -> None:
        result_holder["result"] = runtime_a.execute(call, descriptor)

    execution_thread = threading.Thread(target=_execute)
    execution_thread.start()

    # Simulate worker-side process restart by creating a fresh runtime instance against same DB.
    runtime_b = TenantByocConnectorRuntime(
        worker_jwt_secret="test-secret",
        job_store=SQLiteByocJobQueueStore(db_path),
        result_store=SQLiteByocResultStore(db_path),
        replay_guard=SQLiteReplayGuard(db_path),
        lease_ttl_seconds=2,
    )
    token = runtime_b.issue_worker_token(tenant_id="t1", worker_id="worker-recovery")
    job = _wait_claim(runtime_b, token, "nonce-recovery-claim")
    assert job is not None

    outcome = runtime_b.submit_result(
        tenant_id="t1",
        worker_token=token,
        request_nonce="nonce-recovery-submit-1",
        result=ByocToolResultEnvelope(
            job_id=job["job_id"],
            tenant_id="t1",
            run_id=job["run_id"],
            call_id=job["call_id"],
            tool_name=job["tool_name"],
            status=ByocResultStatus.SUCCESS,
            output={"value": 55},
            idempotency_key=job["idempotency_key"],
            lease_token=job["lease_token"],
        ),
    )
    assert outcome.accepted is True
    execution_thread.join(timeout=4.0)
    result = result_holder.get("result")
    assert result is not None
    assert result.status == ToolStatus.SUCCESS
    assert result.result is not None
    assert result.result["value"] == {"value": 55}


def test_sqlite_cleanup_retention_is_tenant_scoped(tmp_path) -> None:
    db_path = str(tmp_path / "byoc_cleanup.db")
    job_store = SQLiteByocJobQueueStore(db_path)
    result_store = SQLiteByocResultStore(db_path)
    replay_guard = SQLiteReplayGuard(db_path)

    # Tenant t1 completed/cancelled records (eligible for pruning).
    job_store.enqueue(
        ByocToolJobEnvelope(
            job_id="job_t1_done",
            tenant_id="t1",
            run_id="run_t1_done",
            call_id="call_t1_done",
            tool_name="echo_tool",
            arguments={},
            timeout_ms=1000,
            correlation_id="corr_t1_done",
            idempotency_key="idem_t1_done",
        )
    )
    claim_done = job_store.claim_next(tenant_id="t1", worker_id="worker", lease_ttl_seconds=5)
    assert claim_done is not None
    assert job_store.complete_claim(job_id="job_t1_done", lease_token=claim_done.job.lease_token) is True

    job_store.enqueue(
        ByocToolJobEnvelope(
            job_id="job_t1_cancel",
            tenant_id="t1",
            run_id="run_t1_cancel",
            call_id="call_t1_cancel",
            tool_name="echo_tool",
            arguments={},
            timeout_ms=1000,
            correlation_id="corr_t1_cancel",
            idempotency_key="idem_t1_cancel",
        )
    )
    assert job_store.cancel_pending_call(call_id="call_t1_cancel") == 1

    # Tenant t2 record (must remain untouched).
    job_store.enqueue(
        ByocToolJobEnvelope(
            job_id="job_t2_done",
            tenant_id="t2",
            run_id="run_t2_done",
            call_id="call_t2_done",
            tool_name="echo_tool",
            arguments={},
            timeout_ms=1000,
            correlation_id="corr_t2_done",
            idempotency_key="idem_t2_done",
        )
    )
    claim_t2 = job_store.claim_next(tenant_id="t2", worker_id="worker-2", lease_ttl_seconds=5)
    assert claim_t2 is not None
    assert job_store.complete_claim(job_id="job_t2_done", lease_token=claim_t2.job.lease_token) is True

    result_store.ingest(
        ByocToolResultEnvelope(
            job_id="job_t1_done",
            tenant_id="t1",
            run_id="run_t1_done",
            call_id="call_t1_done",
            tool_name="echo_tool",
            status=ByocResultStatus.SUCCESS,
            output={"ok": True},
            idempotency_key="t1:result:1",
            lease_token=claim_done.job.lease_token,
        )
    )
    assert replay_guard.mark_once(key="t1:claim:jti:nonce", ttl_seconds=1) is True
    time.sleep(1.1)

    job_cleanup = job_store.cleanup_retention(
        tenant_id="t1",
        completed_ttl_seconds=1,
        cancelled_ttl_seconds=1,
        max_completed_records=10,
        max_cancelled_records=10,
    )
    result_cleanup = result_store.cleanup_retention(
        tenant_id="t1",
        result_ttl_seconds=1,
        idempotency_ttl_seconds=1,
        max_result_records=10,
    )
    replay_cleanup = replay_guard.cleanup_retention(tenant_id="t1")

    assert job_cleanup["completed_pruned"] >= 1
    assert job_cleanup["cancelled_pruned"] >= 1
    assert result_cleanup["result_payloads_pruned"] >= 1
    assert result_cleanup["idempotency_pruned"] >= 1
    assert replay_cleanup["replay_keys_pruned"] >= 1

    # t2 must remain intact.
    t2_metrics = job_store.health_metrics(tenant_id="t2")
    assert t2_metrics["completed_jobs"] >= 1

