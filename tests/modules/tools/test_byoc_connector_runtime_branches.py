"""
File: test_byoc_connector_runtime_branches.py
Path: tests/modules/tools/test_byoc_connector_runtime_branches.py
Role: Branch-focused unit tests for BYOC connector runtime helper and rejection paths.
Used By:
 - pytest
Depends On:
 - src/tools/byoc/connector_runtime.py
 - src/tools/byoc/job_store.py
 - src/tools/byoc/result_store.py
Notes:
 - Uses lightweight in-test doubles to drive hard-to-reach branch paths deterministically.
"""

from __future__ import annotations

from src.schemas.tool_io import ToolStatus
from src.tools.byoc.connector_runtime import TenantByocConnectorRuntime, _metric_token
from src.tools.byoc.job_contracts import ByocResultStatus, ByocToolJobEnvelope, ByocToolResultEnvelope
from src.tools.byoc.job_store import ByocJobQueueStore, JobLeaseClaim
from src.tools.byoc.result_store import ByocConflictCountRecord, ByocResultIngestOutcome, ByocResultStore, ReplayGuard


def _result_envelope(*, tenant_id: str = "t1", job_id: str = "job_1", lease_token: str = "lease_1") -> ByocToolResultEnvelope:
    return ByocToolResultEnvelope(
        job_id=job_id,
        tenant_id=tenant_id,
        run_id="run_1",
        call_id="call_1",
        tool_name="echo_tool",
        status=ByocResultStatus.SUCCESS,
        output={"ok": True},
        idempotency_key=f"{tenant_id}:call_1:run_1",
        lease_token=lease_token,
    )


class _ReplayGuardDouble(ReplayGuard):
    def __init__(self) -> None:
        self.seen: set[str] = set()

    def mark_once(self, *, key: str, ttl_seconds: int) -> bool:
        normalized = str(key).strip()
        if not normalized:
            return False
        if normalized in self.seen:
            return False
        self.seen.add(normalized)
        return True


class _JobStoreDouble(ByocJobQueueStore):
    def __init__(self) -> None:
        self.cancelled: list[str] = []
        self.replayed: list[str] = []
        self.dead_letter_records: list[dict[str, str]] = []
        self.complete_claim_result = True
        self.leased_job: ByocToolJobEnvelope | None = None

    def enqueue(self, job: ByocToolJobEnvelope) -> None:
        self.leased_job = job

    def claim_next(self, *, tenant_id: str, worker_id: str, lease_ttl_seconds: int) -> JobLeaseClaim | None:
        return None

    def complete_claim(self, *, job_id: str, lease_token: str) -> bool:
        return bool(self.complete_claim_result)

    def get_leased_job(self, *, job_id: str, lease_token: str) -> ByocToolJobEnvelope | None:
        return self.leased_job

    def requeue_expired_leases(self, *, max_claim_attempts_before_dlq: int | None = None) -> int:
        return 0

    def dead_letter_count(self, *, tenant_id: str) -> int:
        return len(self.dead_letter_records)

    def list_dead_letter_jobs(self, *, tenant_id: str, limit: int = 100) -> list[dict[str, str]]:
        return list(self.dead_letter_records[:limit])

    def replay_dead_letter_job(self, *, tenant_id: str, job_id: str) -> bool:
        self.replayed.append(job_id)
        return False

    def cancel_pending_call(self, *, call_id: str) -> int:
        self.cancelled.append(call_id)
        return 0

    def queue_depth(self) -> int:
        return 0


class _ResultStoreDouble(ByocResultStore):
    def __init__(self) -> None:
        self.outcome = ByocResultIngestOutcome(accepted=True, duplicate=False, reason_code="INGESTED")
        self.idempotency_keys: set[str] = set()

    def ingest(self, result: ByocToolResultEnvelope) -> ByocResultIngestOutcome:
        return self.outcome

    def consume(self, job_id: str) -> ByocToolResultEnvelope | None:
        return None

    def has_idempotency_key(self, key: str) -> bool:
        return key in self.idempotency_keys

    def list_conflict_counts(self, *, tenant_id: str) -> list[ByocConflictCountRecord]:
        return []


def test_connector_runtime_nonce_and_webhook_replay_guards() -> None:
    runtime = TenantByocConnectorRuntime(worker_jwt_secret="secret")
    token = runtime.issue_worker_token(tenant_id="t1", worker_id="w1")
    try:
        runtime.claim_next_job(tenant_id="t1", worker_token=token, request_nonce="  ")
    except ValueError as exc:
        assert str(exc) == "WORKER_NONCE_REQUIRED"
    else:
        raise AssertionError("Expected claim nonce validation failure.")

    try:
        runtime.submit_result(
            tenant_id="t1",
            worker_token=token,
            request_nonce="",
            result=_result_envelope(),
        )
    except ValueError as exc:
        assert str(exc) == "WORKER_NONCE_REQUIRED"
    else:
        raise AssertionError("Expected submit nonce validation failure.")

    try:
        runtime.submit_result_webhook(
            tenant_id="t1",
            webhook_secret="secret",
            webhook_request_id="",
            result=_result_envelope(),
        )
    except ValueError as exc:
        assert str(exc) == "WEBHOOK_REQUEST_ID_REQUIRED"
    else:
        raise AssertionError("Expected webhook request id validation failure.")

    try:
        runtime.submit_result_webhook(
            tenant_id="t1",
            webhook_secret="secret",
            webhook_request_id="req-1",
            result=_result_envelope(tenant_id="other"),
        )
    except ValueError as exc:
        assert str(exc) == "WORKER_RESULT_TENANT_MISMATCH"
    else:
        raise AssertionError("Expected tenant mismatch rejection.")
    try:
        runtime.submit_result_webhook(
            tenant_id="t1",
            webhook_secret="secret",
            webhook_request_id="req-1",
            result=_result_envelope(),
        )
    except ValueError as exc:
        assert str(exc) == "WEBHOOK_REQUEST_REPLAYED"
    else:
        raise AssertionError("Expected webhook replay guard rejection.")


def test_connector_runtime_ingest_after_auth_branch_matrix() -> None:
    job_store = _JobStoreDouble()
    result_store = _ResultStoreDouble()
    runtime = TenantByocConnectorRuntime(
        worker_jwt_secret="secret",
        job_store=job_store,
        result_store=result_store,
        replay_guard=_ReplayGuardDouble(),
    )

    try:
        runtime._ingest_result_after_auth(tenant_id="t1", result=_result_envelope(tenant_id="t2"))
    except ValueError as exc:
        assert str(exc) == "WORKER_RESULT_TENANT_MISMATCH"
    else:
        raise AssertionError("Expected tenant mismatch rejection.")

    job_store.leased_job = ByocToolJobEnvelope(
        job_id="job_1",
        tenant_id="t1",
        run_id="run_1",
        call_id="call_1",
        tool_name="echo_tool",
    )
    job_store.complete_claim_result = False
    lease_fail = runtime._ingest_result_after_auth(tenant_id="t1", result=_result_envelope())
    assert lease_fail.accepted is False
    assert lease_fail.reason_code == "BYOC_LEASE_INVALID_OR_EXPIRED"

    job_store.complete_claim_result = True
    result_store.outcome = ByocResultIngestOutcome(accepted=True, duplicate=True, reason_code="IDEMPOTENT_DUPLICATE")
    duplicate = runtime._ingest_result_after_auth(tenant_id="t1", result=_result_envelope())
    assert duplicate.duplicate is True

    result_store.outcome = ByocResultIngestOutcome(accepted=False, duplicate=False, reason_code="BYOC_RESULT_REJECTED")
    rejected = runtime._ingest_result_after_auth(tenant_id="t1", result=_result_envelope())
    assert rejected.accepted is False
    stats = runtime.control_stats_for_tenant(tenant_id="t1")
    assert stats["tenant_rejected_reason_BYOC_RESULT_REJECTED"] >= 1


def test_connector_runtime_misc_helper_branches_and_sqlite_coordinator() -> None:
    runtime = TenantByocConnectorRuntime(
        worker_jwt_secret="secret",
        fair_admission_backend="sqlite",
        fair_admission_sqlite_db_path=":memory:",
        cost_limit_microunits_per_tenant=0,
        budget_partition_limits_microunits={"": 1, "tool:x": "bad"},
    )

    assert runtime.request_cancellation(" ") is False
    assert runtime.drain_progress_events(" ") == []
    runtime._record_progress(call_id=" ", tool_name="echo", state="queued")
    assert runtime.drain_progress_events(" ") == []

    assert runtime._terminal_state(ToolStatus.TIMEOUT) == "timed_out"
    assert runtime._terminal_state(ToolStatus.CANCELLED) == "cancelled"
    assert runtime._terminal_state(ToolStatus.ERROR) == "failed"
    assert runtime._cost_for_status(ToolStatus.TIMEOUT) == runtime._cost_timeout_microunits
    assert runtime._cost_for_status(ToolStatus.CANCELLED) == runtime._cost_cancelled_microunits
    assert runtime._cost_for_status(ToolStatus.ERROR) == runtime._cost_error_microunits
    assert _metric_token("") == "unknown"

    runtime._tenant_partition_cost_window_started_epoch["t1"] = {"tenant": 0}
    runtime._tenant_partition_cost_window_microunits["t1"] = {"tenant": 3}
    p_start, _ = runtime._partition_window_state_unlocked(tenant_id="t1", partition_key="tenant", now=100.0)
    assert p_start == 100
    runtime._tenant_cost_window_started_epoch["t1"] = 0
    runtime._tenant_cost_window_microunits["t1"] = 5
    w_start, _ = runtime._window_state_unlocked(tenant_id="t1", now=200.0)
    assert w_start == 200

    exceeded, reason, details = runtime._cost_limit_exceeded(tenant_id="t1", provider_id="", tool_name="")
    assert exceeded is False
    assert reason == ""
    assert details["partition_limit_microunits"] == runtime._cost_limit_microunits_per_tenant

    coordinator = runtime._fair_admission_coordinator()
    assert coordinator is runtime._fair_admission_coordinator()


def test_connector_runtime_dead_letter_failure_paths_increment_counters() -> None:
    job_store = _JobStoreDouble()
    runtime = TenantByocConnectorRuntime(
        worker_jwt_secret="secret",
        job_store=job_store,
        result_store=_ResultStoreDouble(),
        replay_guard=_ReplayGuardDouble(),
    )
    assert runtime.replay_dead_letter_job(tenant_id="t1", job_id="missing") is False
    batch = runtime.replay_dead_letter_jobs(tenant_id="t1", job_ids=None, limit=5)
    assert batch["attempted"] == 0
    stats = runtime.control_stats()
    assert stats["dlq_replay_failed_total"] >= 1


def test_connector_runtime_submit_replay_and_webhook_auth_paths() -> None:
    runtime = TenantByocConnectorRuntime(worker_jwt_secret="secret")
    token = runtime.issue_worker_token(tenant_id="t1", worker_id="w1")
    first = runtime.submit_result(
        tenant_id="t1",
        worker_token=token,
        request_nonce="nonce-1",
        result=_result_envelope(),
    )
    assert first.accepted is False
    assert first.reason_code == "BYOC_LEASE_INVALID_OR_EXPIRED"
    try:
        runtime.submit_result(
            tenant_id="t1",
            worker_token=token,
            request_nonce="nonce-1",
            result=_result_envelope(),
        )
    except ValueError as exc:
        assert str(exc) == "WORKER_REQUEST_REPLAYED"
    else:
        raise AssertionError("Expected replay rejection for duplicate submit nonce.")

    try:
        runtime.submit_result_webhook(
            tenant_id="t1",
            webhook_secret="wrong",
            webhook_request_id="req-1",
            result=_result_envelope(),
        )
    except ValueError as exc:
        assert str(exc) == "WEBHOOK_AUTH_INVALID"
    else:
        raise AssertionError("Expected webhook auth validation failure.")


def test_connector_runtime_request_cancel_true_and_conflict_metrics_paths() -> None:
    class _JobStoreCancelDouble(_JobStoreDouble):
        def cancel_pending_call(self, *, call_id: str) -> int:
            self.cancelled.append(call_id)
            return 1

        def replay_dead_letter_job(self, *, tenant_id: str, job_id: str) -> bool:
            self.replayed.append(job_id)
            return False

    class _ConflictResultStore(_ResultStoreDouble):
        def list_conflict_counts(self, *, tenant_id: str) -> list[ByocConflictCountRecord]:
            return [
                ByocConflictCountRecord(
                    strategy="first_write_wins",
                    tool_name="echo",
                    tool_version="1.0.0",
                    reason_code="BYOC_RESULT_CONFLICT_REJECTED",
                    count=2,
                )
            ]

    runtime = TenantByocConnectorRuntime(
        worker_jwt_secret="secret",
        fair_admission_enabled=True,
        fair_admission_max_inflight_global=2,
        budget_partition_scope="provider",
        budget_partition_limits_microunits={"provider:openai-test": 10},
        job_store=_JobStoreCancelDouble(),
        result_store=_ConflictResultStore(),
        replay_guard=_ReplayGuardDouble(),
    )
    assert runtime.request_cancellation("call-1") is True
    assert runtime.conflict_counts_for_tenant(tenant_id="t1")
    cleanup = runtime.cleanup_retention(tenant_id="t1", force=True)
    assert set(cleanup.keys()) == {"job_records_pruned", "result_records_pruned", "replay_records_pruned"}
    replay = runtime.replay_dead_letter_jobs(tenant_id="t1", job_ids=["job_a", "", "job_a"], limit=10)
    assert replay["attempted"] == 1
    assert replay["replayed"] == 0
    assert replay["failures"][0]["job_id"] == "job_a"

    stats = runtime.control_stats_for_tenant(tenant_id="t1")
    assert stats["tenant_conflict_total"] == 2
    assert stats["tenant_conflict_reason_byoc_result_conflict_rejected"] == 2
    assert stats["tenant_conflict_strategy_first_write_wins"] == 2
    assert stats["tenant_conflict_tool_echo_version_1_0_0_reason_byoc_result_conflict_rejected"] == 2
    assert runtime.control_stats()["fair_admission_enabled"] == 1


def test_connector_runtime_replay_success_and_provider_partition_limit_resolution() -> None:
    class _JobStoreReplaySuccess(_JobStoreDouble):
        def replay_dead_letter_job(self, *, tenant_id: str, job_id: str) -> bool:
            return job_id == "job_ok"

    runtime = TenantByocConnectorRuntime(
        worker_jwt_secret="secret",
        budget_partition_scope="per_provider",
        budget_partition_limits_microunits={"provider:openai-test": 11},
        job_store=_JobStoreReplaySuccess(),
        result_store=_ResultStoreDouble(),
        replay_guard=_ReplayGuardDouble(),
    )
    replay = runtime.replay_dead_letter_jobs(tenant_id="t1", job_ids=["job_ok"], limit=10)
    assert replay["attempted"] == 1
    assert replay["replayed"] == 1
    assert replay["failures"] == []
    key, limit, partitioned = runtime._resolve_partition_limit(
        tenant_id="t1",
        provider_id="openai-test",
        tool_name="echo_tool",
    )
    assert key == "provider:openai-test"
    assert limit == 11
    assert partitioned is True
