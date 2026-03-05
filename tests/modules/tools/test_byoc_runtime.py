"""
File: test_byoc_runtime.py
Path: tests/modules/tools/test_byoc_runtime.py
Role: Contract tests for BYOC pull-worker runtime skeleton.
Used By:
 - pytest
Depends On:
 - src/tools/byoc/connector_runtime.py
 - src/tools/registry.py
Notes:
 - Validates queue/claim/submit flow and idempotent result ingestion.
"""

from __future__ import annotations

import threading
import time

from src.schemas.tool_io import ToolCallContext, ToolStatus
from src.tools.byoc.connector_runtime import TenantByocConnectorRuntime
from src.tools.byoc.job_contracts import ByocResultStatus, ByocToolResultEnvelope
from src.tools.registry import ToolDescriptor


def _call() -> ToolCallContext:
    return ToolCallContext(
        schema_version="1.0",
        call_id="call_byoc_1",
        session_id="sess_1",
        run_id="run_1",
        job_id="job_1",
        task_id="task_1",
        agent_id="agent_1",
        provider_id="openai-test",
        tool_name="echo_tool",
        arguments={"value": 42},
        tenant_id="t1",
    )


def _descriptor() -> ToolDescriptor:
    return ToolDescriptor(name="echo_tool", handler=lambda value: value, timeout_ms=1500)


def _wait_claim(runtime: TenantByocConnectorRuntime, token: str, nonce_prefix: str) -> dict[str, object] | None:
    deadline = time.time() + 1.5
    attempt = 0
    while time.time() < deadline:
        attempt += 1
        job = runtime.claim_next_job(
            tenant_id="t1",
            worker_token=token,
            request_nonce=f"{nonce_prefix}-{attempt}",
        )
        if job is not None:
            return job
        time.sleep(0.02)
    return None


def test_byoc_runtime_enqueue_claim_submit_happy_path() -> None:
    runtime = TenantByocConnectorRuntime(worker_jwt_secret="test-secret")
    call = _call()
    descriptor = _descriptor()
    token = runtime.issue_worker_token(tenant_id="t1", worker_id="worker-1")
    result_holder: dict[str, object] = {}

    def _execute() -> None:
        result_holder["result"] = runtime.execute(call, descriptor)

    thread = threading.Thread(target=_execute)
    thread.start()
    job = _wait_claim(runtime, token, "nonce-claim-001")
    assert job is not None
    assert job["call_id"] == "call_byoc_1"
    assert job["tool_name"] == "echo_tool"

    outcome = runtime.submit_result(
        tenant_id="t1",
        worker_token=token,
        result=ByocToolResultEnvelope(
            job_id=job["job_id"],
            tenant_id="t1",
            run_id=job["run_id"],
            call_id=job["call_id"],
            tool_name=job["tool_name"],
            status=ByocResultStatus.SUCCESS,
            output={"value": 42},
            idempotency_key=job["idempotency_key"],
            lease_token=job["lease_token"],
        ),
        request_nonce="nonce-submit-001",
    )
    assert outcome.accepted is True
    assert outcome.duplicate is False
    thread.join(timeout=2.0)
    result = result_holder["result"]
    assert result.status == ToolStatus.SUCCESS
    assert result.result is not None
    assert result.result["value"] == {"value": 42}


def test_byoc_claim_includes_active_version_metadata() -> None:
    runtime = TenantByocConnectorRuntime(worker_jwt_secret="test-secret")
    call = _call()
    descriptor = ToolDescriptor(
        name="echo_tool",
        handler=lambda value: value,
        timeout_ms=200,
        metadata={
            "tool_version": "2.0.0",
            "package_ref": "pkg://echo/2.0.0",
            "entry_file": "handler.py",
            "entrypoint": "run",
            "artifact_bundle_hash_sha256": "hash-v2",
            "artifact_bundle_signature_hmac_sha256": "sig-v2",
            "artifact_signature_version": "v1",
        },
    )
    token = runtime.issue_worker_token(tenant_id="t1", worker_id="worker-1")
    thread = threading.Thread(target=lambda: runtime.execute(call, descriptor))
    thread.start()
    job = _wait_claim(runtime, token, "nonce-claim-version-meta")
    assert job is not None
    assert job["tool_version"] == "2.0.0"
    assert job["package_ref"] == "pkg://echo/2.0.0"
    assert job["entry_file"] == "handler.py"
    assert job["entrypoint"] == "run"
    assert job["artifact_bundle_hash_sha256"] == "hash-v2"
    assert job["artifact_bundle_signature_hmac_sha256"] == "sig-v2"
    assert job["artifact_signature_version"] == "v1"
    runtime.submit_result(
        tenant_id="t1",
        worker_token=token,
        result=ByocToolResultEnvelope(
            job_id=job["job_id"],
            tenant_id="t1",
            run_id=job["run_id"],
            call_id=job["call_id"],
            tool_name=job["tool_name"],
            status=ByocResultStatus.SUCCESS,
            output={"value": 42},
            idempotency_key=job["idempotency_key"],
            lease_token=job["lease_token"],
            tool_version="2.0.0",
            artifact_bundle_hash_sha256="hash-v2",
            artifact_bundle_signature_hmac_sha256="sig-v2",
            artifact_signature_version="v1",
        ),
        request_nonce="nonce-submit-version-meta",
    )
    thread.join(timeout=2.0)


def test_byoc_runtime_duplicate_submit_is_idempotent_noop() -> None:
    runtime = TenantByocConnectorRuntime(worker_jwt_secret="test-secret")
    call = _call()
    descriptor = _descriptor()
    token = runtime.issue_worker_token(tenant_id="t1", worker_id="worker-1")
    result_holder: dict[str, object] = {}

    def _execute() -> None:
        result_holder["result"] = runtime.execute(call, descriptor)

    thread = threading.Thread(target=_execute)
    thread.start()
    job = _wait_claim(runtime, token, "nonce-claim-002")
    assert job is not None

    first = runtime.submit_result(
        tenant_id="t1",
        worker_token=token,
        result=ByocToolResultEnvelope(
            job_id=job["job_id"],
            tenant_id="t1",
            run_id=job["run_id"],
            call_id=job["call_id"],
            tool_name=job["tool_name"],
            status=ByocResultStatus.SUCCESS,
            output={"value": 1},
            idempotency_key=job["idempotency_key"],
            lease_token=job["lease_token"],
        ),
        request_nonce="nonce-submit-002",
    )
    second = runtime.submit_result(
        tenant_id="t1",
        worker_token=token,
        result=ByocToolResultEnvelope(
            job_id=job["job_id"],
            tenant_id="t1",
            run_id=job["run_id"],
            call_id=job["call_id"],
            tool_name=job["tool_name"],
            status=ByocResultStatus.SUCCESS,
            output={"value": 999},
            idempotency_key=job["idempotency_key"],
            lease_token=job["lease_token"],
        ),
        request_nonce="nonce-submit-003",
    )
    thread.join(timeout=2.0)
    result = result_holder["result"]
    assert first.accepted is True and first.duplicate is False
    assert second.accepted is True and second.duplicate is True
    assert result.status == ToolStatus.SUCCESS
    assert result.result is not None
    assert result.result["value"] == {"value": 1}


def test_byoc_runtime_rejects_invalid_worker_token() -> None:
    runtime = TenantByocConnectorRuntime(worker_jwt_secret="test-secret")
    try:
        runtime.claim_next_job(
            tenant_id="t1",
            worker_token="bad-token",
            request_nonce="nonce-invalid-001",
        )
    except ValueError as exc:
        assert str(exc) in {"WORKER_TOKEN_INVALID", "WORKER_TOKEN_EXPIRED", "WORKER_TOKEN_TENANT_MISMATCH"}
    else:
        raise AssertionError("Expected invalid token rejection.")


def test_byoc_runtime_requeues_expired_lease_then_reclaims() -> None:
    runtime = TenantByocConnectorRuntime(
        worker_jwt_secret="test-secret",
        lease_ttl_seconds=1,
    )
    call = _call()
    descriptor = _descriptor()
    token = runtime.issue_worker_token(tenant_id="t1", worker_id="worker-1")
    result_holder: dict[str, object] = {}

    def _execute() -> None:
        result_holder["result"] = runtime.execute(call, descriptor)

    thread = threading.Thread(target=_execute)
    thread.start()

    first_claim = _wait_claim(runtime, token, "nonce-claim-003")
    assert first_claim is not None

    time.sleep(1.2)

    second_claim = _wait_claim(runtime, token, "nonce-claim-004")
    assert second_claim is not None
    assert second_claim["job_id"] == first_claim["job_id"]
    assert second_claim["claim_attempt"] >= 2

    outcome = runtime.submit_result(
        tenant_id="t1",
        worker_token=token,
        request_nonce="nonce-submit-004",
        result=ByocToolResultEnvelope(
            job_id=second_claim["job_id"],
            tenant_id="t1",
            run_id=second_claim["run_id"],
            call_id=second_claim["call_id"],
            tool_name=second_claim["tool_name"],
            status=ByocResultStatus.SUCCESS,
            output={"value": 77},
            idempotency_key=second_claim["idempotency_key"],
            lease_token=second_claim["lease_token"],
        ),
    )
    assert outcome.accepted is True
    thread.join(timeout=2.0)
    result = result_holder["result"]
    assert result.status == ToolStatus.SUCCESS
    assert result.result is not None
    assert result.result["value"] == {"value": 77}


def test_byoc_runtime_rejects_replayed_nonce() -> None:
    runtime = TenantByocConnectorRuntime(worker_jwt_secret="test-secret")
    token = runtime.issue_worker_token(tenant_id="t1", worker_id="worker-1")
    first = runtime.claim_next_job(
        tenant_id="t1",
        worker_token=token,
        request_nonce="nonce-replay-001",
    )
    second_error = None
    try:
        runtime.claim_next_job(
            tenant_id="t1",
            worker_token=token,
            request_nonce="nonce-replay-001",
        )
    except ValueError as exc:
        second_error = str(exc)
    assert first is None
    assert second_error == "WORKER_REQUEST_REPLAYED"


def test_byoc_runtime_duplicate_callback_race_is_idempotent() -> None:
    runtime = TenantByocConnectorRuntime(worker_jwt_secret="test-secret")
    call = _call()
    descriptor = _descriptor()
    token = runtime.issue_worker_token(tenant_id="t1", worker_id="worker-race")
    result_holder: dict[str, object] = {}

    def _execute() -> None:
        result_holder["result"] = runtime.execute(call, descriptor)

    run_thread = threading.Thread(target=_execute)
    run_thread.start()
    job = _wait_claim(runtime, token, "nonce-race-claim-001")
    assert job is not None

    outcomes: list[tuple[bool, bool, str]] = []

    def _submit(index: int) -> None:
        out = runtime.submit_result(
            tenant_id="t1",
            worker_token=token,
            request_nonce=f"nonce-race-submit-00{index}",
            result=ByocToolResultEnvelope(
                job_id=job["job_id"],
                tenant_id="t1",
                run_id=job["run_id"],
                call_id=job["call_id"],
                tool_name=job["tool_name"],
                status=ByocResultStatus.SUCCESS,
                output={"winner": index},
                idempotency_key=job["idempotency_key"],
                lease_token=job["lease_token"],
            ),
        )
        outcomes.append((out.accepted, out.duplicate, out.reason_code))

    t1 = threading.Thread(target=_submit, args=(1,))
    t2 = threading.Thread(target=_submit, args=(2,))
    t1.start()
    t2.start()
    t1.join(timeout=2.0)
    t2.join(timeout=2.0)
    run_thread.join(timeout=2.0)

    assert len(outcomes) == 2
    assert sum(1 for accepted, duplicate, _ in outcomes if accepted and not duplicate) == 1
    assert sum(1 for accepted, duplicate, _ in outcomes if accepted and duplicate) == 1
    result = result_holder["result"]
    assert result.status == ToolStatus.SUCCESS


def test_byoc_runtime_progress_events_include_job_and_lease_metadata() -> None:
    runtime = TenantByocConnectorRuntime(worker_jwt_secret="test-secret")
    call = _call()
    descriptor = _descriptor()
    token = runtime.issue_worker_token(tenant_id="t1", worker_id="worker-progress")
    result_holder: dict[str, object] = {}

    def _execute() -> None:
        result_holder["result"] = runtime.execute(call, descriptor)

    run_thread = threading.Thread(target=_execute)
    run_thread.start()
    job = _wait_claim(runtime, token, "nonce-progress-claim-001")
    assert job is not None
    outcome = runtime.submit_result(
        tenant_id="t1",
        worker_token=token,
        request_nonce="nonce-progress-submit-001",
        result=ByocToolResultEnvelope(
            job_id=job["job_id"],
            tenant_id="t1",
            run_id=job["run_id"],
            call_id=job["call_id"],
            tool_name=job["tool_name"],
            status=ByocResultStatus.SUCCESS,
            output={"value": 22},
            idempotency_key=job["idempotency_key"],
            lease_token=job["lease_token"],
        ),
    )
    assert outcome.accepted is True
    run_thread.join(timeout=2.0)
    progress = runtime.drain_progress_events(call.call_id)
    assert [entry["state"] for entry in progress] == ["queued", "running", "completed"]
    assert all(str(entry.get("job_id", "")).startswith("job_") for entry in progress)
    running = next(entry for entry in progress if entry["state"] == "running")
    assert str(running.get("lease_token", "")).startswith("lease_")
    assert str(running.get("lease_expires_at_epoch", "")).isdigit()
    assert str(running.get("claim_attempt", "")) == "1"


def test_byoc_result_maps_artifact_integrity_metadata_into_runtime_payload() -> None:
    runtime = TenantByocConnectorRuntime(worker_jwt_secret="test-secret")
    call = _call()
    descriptor = ToolDescriptor(
        name="echo_tool",
        handler=lambda value: value,
        timeout_ms=1500,
        metadata={
            "tool_version": "3.0.0",
            "artifact_bundle_hash_sha256": "hash-v3",
            "artifact_bundle_signature_hmac_sha256": "sig-v3",
            "artifact_signature_version": "v2",
        },
    )
    token = runtime.issue_worker_token(tenant_id="t1", worker_id="worker-meta")
    result_holder: dict[str, object] = {}

    def _execute() -> None:
        result_holder["result"] = runtime.execute(call, descriptor)

    thread = threading.Thread(target=_execute)
    thread.start()
    job = _wait_claim(runtime, token, "nonce-meta-claim-001")
    assert job is not None
    runtime.submit_result(
        tenant_id="t1",
        worker_token=token,
        request_nonce="nonce-meta-submit-001",
        result=ByocToolResultEnvelope(
            job_id=job["job_id"],
            tenant_id="t1",
            run_id=job["run_id"],
            call_id=job["call_id"],
            tool_name=job["tool_name"],
            status=ByocResultStatus.SUCCESS,
            output={"value": 42},
            idempotency_key=job["idempotency_key"],
            lease_token=job["lease_token"],
            tool_version="3.0.0",
            artifact_bundle_hash_sha256="hash-v3",
            artifact_bundle_signature_hmac_sha256="sig-v3",
            artifact_signature_version="v2",
        ),
    )
    thread.join(timeout=2.0)
    result = result_holder["result"]
    assert result.status == ToolStatus.SUCCESS
    assert result.result is not None
    runtime_meta = result.result.get("runtime", {})
    assert runtime_meta.get("artifact_bundle_hash_sha256") == "hash-v3"
    assert runtime_meta.get("artifact_bundle_signature_hmac_sha256") == "sig-v3"
    assert runtime_meta.get("artifact_signature_version") == "v2"


def test_byoc_submit_rejects_artifact_integrity_mismatch() -> None:
    runtime = TenantByocConnectorRuntime(worker_jwt_secret="test-secret")
    call = _call()
    descriptor = ToolDescriptor(
        name="echo_tool",
        handler=lambda value: value,
        timeout_ms=1500,
        metadata={
            "artifact_bundle_hash_sha256": "hash-expected",
            "artifact_bundle_signature_hmac_sha256": "sig-expected",
            "artifact_signature_version": "v1",
        },
    )
    token = runtime.issue_worker_token(tenant_id="t1", worker_id="worker-integrity")
    run_thread = threading.Thread(target=lambda: runtime.execute(call, descriptor))
    run_thread.start()
    job = _wait_claim(runtime, token, "nonce-integrity-claim-001")
    assert job is not None
    outcome = runtime.submit_result(
        tenant_id="t1",
        worker_token=token,
        request_nonce="nonce-integrity-submit-001",
        result=ByocToolResultEnvelope(
            job_id=job["job_id"],
            tenant_id="t1",
            run_id=job["run_id"],
            call_id=job["call_id"],
            tool_name=job["tool_name"],
            status=ByocResultStatus.SUCCESS,
            output={"value": 1},
            idempotency_key=job["idempotency_key"],
            lease_token=job["lease_token"],
            artifact_bundle_hash_sha256="hash-tampered",
            artifact_bundle_signature_hmac_sha256="sig-expected",
            artifact_signature_version="v1",
        ),
    )
    assert outcome.accepted is False
    assert outcome.reason_code == "BYOC_ARTIFACT_INTEGRITY_MISMATCH"
    run_thread.join(timeout=1.0)


def test_byoc_submit_rejects_signature_version_mismatch() -> None:
    runtime = TenantByocConnectorRuntime(worker_jwt_secret="test-secret")
    call = _call()
    descriptor = ToolDescriptor(
        name="echo_tool",
        handler=lambda value: value,
        timeout_ms=200,
        metadata={
            "artifact_bundle_hash_sha256": "hash-expected",
            "artifact_bundle_signature_hmac_sha256": "sig-expected",
            "artifact_signature_version": "v2",
        },
    )
    token = runtime.issue_worker_token(tenant_id="t1", worker_id="worker-integrity-version")
    run_thread = threading.Thread(target=lambda: runtime.execute(call, descriptor))
    run_thread.start()
    job = _wait_claim(runtime, token, "nonce-version-claim-001")
    assert job is not None
    outcome = runtime.submit_result(
        tenant_id="t1",
        worker_token=token,
        request_nonce="nonce-version-submit-001",
        result=ByocToolResultEnvelope(
            job_id=job["job_id"],
            tenant_id="t1",
            run_id=job["run_id"],
            call_id=job["call_id"],
            tool_name=job["tool_name"],
            status=ByocResultStatus.SUCCESS,
            output={"value": 2},
            idempotency_key=job["idempotency_key"],
            lease_token=job["lease_token"],
            artifact_bundle_hash_sha256="hash-expected",
            artifact_bundle_signature_hmac_sha256="sig-expected",
            artifact_signature_version="v1",
        ),
    )
    assert outcome.accepted is False
    assert outcome.reason_code == "BYOC_ARTIFACT_SIGNATURE_VERSION_MISMATCH"
    run_thread.join(timeout=1.0)


def test_byoc_runtime_moves_expired_lease_to_dlq_and_replays() -> None:
    runtime = TenantByocConnectorRuntime(
        worker_jwt_secret="test-secret",
        lease_ttl_seconds=1,
        max_claim_attempts_before_dlq=1,
    )
    call = _call()
    descriptor = _descriptor()
    token = runtime.issue_worker_token(tenant_id="t1", worker_id="worker-dlq")
    result_holder: dict[str, object] = {}

    def _execute() -> None:
        result_holder["result"] = runtime.execute(call, descriptor)

    thread = threading.Thread(target=_execute)
    thread.start()
    first_claim = _wait_claim(runtime, token, "nonce-dlq-claim-001")
    assert first_claim is not None
    time.sleep(1.2)

    second_claim = runtime.claim_next_job(
        tenant_id="t1",
        worker_token=token,
        request_nonce="nonce-dlq-claim-002",
    )
    assert second_claim is None

    dlq_records = runtime.list_dead_letter_jobs(tenant_id="t1", limit=10)
    assert len(dlq_records) == 1
    assert dlq_records[0]["job_id"] == first_claim["job_id"]
    assert dlq_records[0]["dead_letter_reason_code"] == "BYOC_LEASE_RETRY_EXHAUSTED"

    replayed = runtime.replay_dead_letter_job(tenant_id="t1", job_id=first_claim["job_id"])
    assert replayed is True
    replay_claim = _wait_claim(runtime, token, "nonce-dlq-claim-003")
    assert replay_claim is not None
    assert replay_claim["job_id"] == first_claim["job_id"]

    outcome = runtime.submit_result(
        tenant_id="t1",
        worker_token=token,
        request_nonce="nonce-dlq-submit-001",
        result=ByocToolResultEnvelope(
            job_id=replay_claim["job_id"],
            tenant_id="t1",
            run_id=replay_claim["run_id"],
            call_id=replay_claim["call_id"],
            tool_name=replay_claim["tool_name"],
            status=ByocResultStatus.SUCCESS,
            output={"value": 12},
            idempotency_key=replay_claim["idempotency_key"],
            lease_token=replay_claim["lease_token"],
        ),
    )
    assert outcome.accepted is True
    thread.join(timeout=2.0)
    result = result_holder["result"]
    assert result.status == ToolStatus.SUCCESS


def test_byoc_runtime_emits_tenant_cost_counters() -> None:
    runtime = TenantByocConnectorRuntime(
        worker_jwt_secret="test-secret",
        cost_success_microunits=7,
        cost_error_microunits=11,
        cost_timeout_microunits=13,
        cost_cancelled_microunits=5,
    )
    call = _call()
    descriptor = _descriptor()
    token = runtime.issue_worker_token(tenant_id="t1", worker_id="worker-cost")
    result_holder: dict[str, object] = {}

    def _execute() -> None:
        result_holder["result"] = runtime.execute(call, descriptor)

    thread = threading.Thread(target=_execute)
    thread.start()
    claim = _wait_claim(runtime, token, "nonce-cost-claim-001")
    assert claim is not None
    outcome = runtime.submit_result(
        tenant_id="t1",
        worker_token=token,
        request_nonce="nonce-cost-submit-001",
        result=ByocToolResultEnvelope(
            job_id=claim["job_id"],
            tenant_id="t1",
            run_id=claim["run_id"],
            call_id=claim["call_id"],
            tool_name=claim["tool_name"],
            status=ByocResultStatus.SUCCESS,
            output={"value": 1},
            idempotency_key=claim["idempotency_key"],
            lease_token=claim["lease_token"],
        ),
    )
    assert outcome.accepted is True
    thread.join(timeout=2.0)
    assert result_holder["result"].status == ToolStatus.SUCCESS
    stats = runtime.control_stats_for_tenant(tenant_id="t1")
    assert stats["tenant_submit_attempts_total"] == 1
    assert stats["tenant_cost_microunits_total"] == 7
    assert stats["tenant_cost_remaining_microunits"] == stats["tenant_cost_limit_microunits"] - 7


def test_byoc_runtime_rejects_execute_when_cost_limit_exceeded() -> None:
    runtime = TenantByocConnectorRuntime(
        worker_jwt_secret="test-secret",
        enforce_cost_limit=True,
        cost_limit_microunits_per_tenant=1,
        cost_success_microunits=2,
    )
    call = _call()
    descriptor = _descriptor()
    token = runtime.issue_worker_token(tenant_id="t1", worker_id="worker-limit")
    result_holder: dict[str, object] = {}

    def _execute_first() -> None:
        result_holder["first"] = runtime.execute(call, descriptor)

    first_thread = threading.Thread(target=_execute_first)
    first_thread.start()
    claim = _wait_claim(runtime, token, "nonce-limit-claim-001")
    assert claim is not None
    first_submit = runtime.submit_result(
        tenant_id="t1",
        worker_token=token,
        request_nonce="nonce-limit-submit-001",
        result=ByocToolResultEnvelope(
            job_id=claim["job_id"],
            tenant_id="t1",
            run_id=claim["run_id"],
            call_id=claim["call_id"],
            tool_name=claim["tool_name"],
            status=ByocResultStatus.SUCCESS,
            output={"value": 2},
            idempotency_key=claim["idempotency_key"],
            lease_token=claim["lease_token"],
        ),
    )
    assert first_submit.accepted is True
    first_thread.join(timeout=2.0)
    assert result_holder["first"].status == ToolStatus.SUCCESS

    second = runtime.execute(call, descriptor)
    assert second.status == ToolStatus.ERROR
    assert second.error.code == "BYOC_COST_LIMIT_EXCEEDED"
    stats = runtime.control_stats_for_tenant(tenant_id="t1")
    assert stats["tenant_rejected_reason_BYOC_COST_LIMIT_EXCEEDED"] >= 1

