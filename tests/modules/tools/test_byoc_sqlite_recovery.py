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
from pathlib import Path

from src.schemas.tool_io import ToolCallContext, ToolStatus
from src.tools.byoc.connector_runtime import TenantByocConnectorRuntime
from src.tools.byoc.job_contracts import ByocResultStatus, ByocToolJobEnvelope, ByocToolResultEnvelope
from src.tools.byoc.result_store import ByocResultConflictStrategy
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


def _call_for_index(index: int) -> ToolCallContext:
    return ToolCallContext(
        schema_version="1.0",
        call_id=f"call_sqlite_{index}",
        session_id=f"sess_sqlite_{index}",
        run_id=f"run_sqlite_{index}",
        job_id=f"job_sqlite_{index}",
        task_id=f"task_sqlite_{index}",
        agent_id="agent_sqlite_storm",
        provider_id="openai-test",
        tool_name="echo_tool",
        arguments={"value": index},
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


def test_sqlite_job_store_lease_expiry_storm_routes_to_dlq(tmp_path: Path) -> None:
    db_path = str(tmp_path / "byoc_lease_storm.db")
    store = SQLiteByocJobQueueStore(db_path)
    tenant_id = "t1"
    total_jobs = 12
    for idx in range(total_jobs):
        store.enqueue(
            ByocToolJobEnvelope(
                job_id=f"job_storm_{idx}",
                tenant_id=tenant_id,
                run_id=f"run_storm_{idx}",
                call_id=f"call_storm_{idx}",
                tool_name="echo_tool",
                arguments={"value": idx},
                timeout_ms=1200,
                correlation_id=f"corr_storm_{idx}",
                idempotency_key=f"idem_storm_{idx}",
            )
        )

    for _ in range(2):
        claimed = 0
        while True:
            lease = store.claim_next(tenant_id=tenant_id, worker_id="worker-storm", lease_ttl_seconds=1)
            if lease is None:
                break
            claimed += 1
        assert claimed == total_jobs
        time.sleep(1.1)
        store.requeue_expired_leases(max_claim_attempts_before_dlq=2)

    assert store.queue_depth() == 0
    assert store.dead_letter_count(tenant_id=tenant_id) == total_jobs
    records = store.list_dead_letter_jobs(tenant_id=tenant_id, limit=20)
    assert len(records) == total_jobs
    assert all(row["dead_letter_reason_code"] == "BYOC_LEASE_RETRY_EXHAUSTED" for row in records)


def test_byoc_runtime_sqlite_restart_race_recovers_under_parallel_load(tmp_path: Path) -> None:
    db_path = str(tmp_path / "byoc_restart_race.db")
    runtime_a = TenantByocConnectorRuntime(
        worker_jwt_secret="test-secret",
        job_store=SQLiteByocJobQueueStore(db_path),
        result_store=SQLiteByocResultStore(db_path),
        replay_guard=SQLiteReplayGuard(db_path),
        lease_ttl_seconds=2,
    )
    runtime_b = TenantByocConnectorRuntime(
        worker_jwt_secret="test-secret",
        job_store=SQLiteByocJobQueueStore(db_path),
        result_store=SQLiteByocResultStore(db_path),
        replay_guard=SQLiteReplayGuard(db_path),
        lease_ttl_seconds=2,
    )
    token = runtime_b.issue_worker_token(tenant_id="t1", worker_id="worker-race")
    descriptor = _descriptor()
    total_calls = 10
    threads: list[threading.Thread] = []
    results: dict[int, object] = {}

    def _execute(index: int) -> None:
        results[index] = runtime_a.execute(_call_for_index(index), descriptor)

    for idx in range(total_calls):
        thread = threading.Thread(target=_execute, args=(idx,))
        threads.append(thread)
        thread.start()

    seen_jobs: set[str] = set()
    deadline = time.time() + 10.0
    claim_attempt = 0
    while len(seen_jobs) < total_calls and time.time() < deadline:
        claim_attempt += 1
        claim = runtime_b.claim_next_job(
            tenant_id="t1",
            worker_token=token,
            request_nonce=f"nonce-race-claim-{claim_attempt}",
        )
        if claim is None:
            time.sleep(0.02)
            continue
        seen_jobs.add(str(claim["job_id"]))
        outcome = runtime_b.submit_result(
            tenant_id="t1",
            worker_token=token,
            request_nonce=f"nonce-race-submit-{len(seen_jobs)}",
            result=ByocToolResultEnvelope(
                job_id=str(claim["job_id"]),
                tenant_id="t1",
                run_id=str(claim["run_id"]),
                call_id=str(claim["call_id"]),
                tool_name=str(claim["tool_name"]),
                status=ByocResultStatus.SUCCESS,
                output={"value": claim["arguments"]["value"]},
                idempotency_key=str(claim["idempotency_key"]),
                lease_token=str(claim["lease_token"]),
            ),
        )
        assert outcome.accepted is True

    assert len(seen_jobs) == total_calls
    for thread in threads:
        thread.join(timeout=6.0)
        assert not thread.is_alive()
    assert len(results) == total_calls
    for result in results.values():
        assert result.status == ToolStatus.SUCCESS


def test_byoc_runtime_sqlite_replay_collision_under_submit_pressure(tmp_path: Path) -> None:
    db_path = str(tmp_path / "byoc_replay_collision.db")
    runtime = TenantByocConnectorRuntime(
        worker_jwt_secret="test-secret",
        job_store=SQLiteByocJobQueueStore(db_path),
        result_store=SQLiteByocResultStore(db_path),
        replay_guard=SQLiteReplayGuard(db_path),
    )
    descriptor = _descriptor()
    result_holder: dict[str, object] = {}

    def _execute() -> None:
        result_holder["result"] = runtime.execute(_call(), descriptor)

    execution_thread = threading.Thread(target=_execute)
    execution_thread.start()
    token = runtime.issue_worker_token(tenant_id="t1", worker_id="worker-replay-collision")
    claim = _wait_claim(runtime, token, "nonce-replay-collision-claim")
    assert claim is not None

    accepted_outcomes: list[object] = []
    replay_errors: list[str] = []
    submit_nonce = "nonce-replay-collision-submit"
    gate = threading.Barrier(5)

    def _submit() -> None:
        gate.wait()
        try:
            outcome = runtime.submit_result(
                tenant_id="t1",
                worker_token=token,
                request_nonce=submit_nonce,
                result=ByocToolResultEnvelope(
                    job_id=str(claim["job_id"]),
                    tenant_id="t1",
                    run_id=str(claim["run_id"]),
                    call_id=str(claim["call_id"]),
                    tool_name=str(claim["tool_name"]),
                    status=ByocResultStatus.SUCCESS,
                    output={"value": 55},
                    idempotency_key=str(claim["idempotency_key"]),
                    lease_token=str(claim["lease_token"]),
                ),
            )
            accepted_outcomes.append(outcome)
        except ValueError as exc:
            replay_errors.append(str(exc))

    submit_threads = [threading.Thread(target=_submit) for _ in range(5)]
    for thread in submit_threads:
        thread.start()
    for thread in submit_threads:
        thread.join(timeout=3.0)
        assert not thread.is_alive()

    execution_thread.join(timeout=4.0)
    assert result_holder["result"].status == ToolStatus.SUCCESS
    assert len(accepted_outcomes) == 1
    assert all(item == "WORKER_REQUEST_REPLAYED" for item in replay_errors)
    assert len(replay_errors) == 4


def test_sqlite_result_store_conflict_strategy_under_bulk_load(tmp_path: Path) -> None:
    db_path = str(tmp_path / "byoc_conflict_load.db")
    store = SQLiteByocResultStore(
        str(db_path),
        conflict_strategy=ByocResultConflictStrategy.PREFER_SUCCESS,
    )
    total_jobs = 40
    for idx in range(total_jobs):
        first = store.ingest(
            ByocToolResultEnvelope(
                job_id=f"job_conflict_{idx}",
                tenant_id="t1",
                run_id=f"run_conflict_{idx}",
                call_id=f"call_conflict_{idx}",
                tool_name="echo_tool",
                status=ByocResultStatus.ERROR,
                output={"value": idx},
                idempotency_key=f"t1:{idx}:a",
                lease_token=f"lease_{idx}",
            )
        )
        second = store.ingest(
            ByocToolResultEnvelope(
                job_id=f"job_conflict_{idx}",
                tenant_id="t1",
                run_id=f"run_conflict_{idx}",
                call_id=f"call_conflict_{idx}",
                tool_name="echo_tool",
                status=ByocResultStatus.SUCCESS,
                output={"value": idx + 1000},
                idempotency_key=f"t1:{idx}:b",
                lease_token=f"lease_{idx}",
            )
        )
        assert first.accepted is True
        assert second.accepted is True
        assert second.reason_code == "BYOC_RESULT_CONFLICT_REPLACED"

    for idx in range(total_jobs):
        result = store.consume(f"job_conflict_{idx}")
        assert result is not None
        assert result.status == ByocResultStatus.SUCCESS
        assert result.output["value"] == idx + 1000

