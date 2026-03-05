"""
File: test_byoc_runtime_control_api.py
Path: tests/modules/api/test_byoc_runtime_control_api.py
Role: API tests for BYOC runtime-control pull-worker endpoints.
Used By:
 - pytest
Depends On:
 - src/api/bootstrap.py
 - src/config/settings.py
Notes:
 - Exercises token issuance, claim, submit, and auth failure paths.
"""

from __future__ import annotations

import json
import threading

from fastapi.testclient import TestClient

from src.api.bootstrap import build_test_app
from src.config.settings import AppSettings, RuntimeSettings


def _headers(tenant_id: str = "t1") -> dict[str, str]:
    payload = {
        "subject": "admin@test.com",
        "roles": ["admin"],
        "tenant_id": tenant_id,
        "token_validation_state": "valid",
    }
    return {"X-Identity": json.dumps(payload)}


def _byoc_client(
    *,
    max_claim_attempts_before_dlq: int = 3,
    lease_ttl_seconds: int = 30,
    enable_cost_window_policy: bool = False,
    cost_window_seconds: int = 3600,
    anomaly_detection_enabled: bool = True,
    anomaly_rejection_rate_threshold: float = 0.2,
    anomaly_min_submit_attempts: int = 5,
    anomaly_min_rejection_count: int = 3,
    fair_admission_enabled: bool = False,
    fair_admission_max_inflight_global: int = 8,
    fair_admission_wait_timeout_ms: int = 1000,
) -> TestClient:
    settings = AppSettings(
        schema_version="1.0",
        environment="test",
        runtime=RuntimeSettings(
            default_provider_id="openai-test",
            allowed_provider_ids=["openai-test"],
            require_provider_healthcheck_on_start=False,
            enable_byoc_tool_runtime=True,
            byoc_worker_jwt_secret="test-secret",
            byoc_lease_ttl_seconds=lease_ttl_seconds,
            byoc_max_claim_attempts_before_dlq=max_claim_attempts_before_dlq,
            byoc_enable_cost_window_policy=enable_cost_window_policy,
            byoc_cost_window_seconds=cost_window_seconds,
            byoc_anomaly_detection_enabled=anomaly_detection_enabled,
            byoc_anomaly_rejection_rate_threshold=anomaly_rejection_rate_threshold,
            byoc_anomaly_min_submit_attempts=anomaly_min_submit_attempts,
            byoc_anomaly_min_rejection_count=anomaly_min_rejection_count,
            byoc_fair_admission_enabled=fair_admission_enabled,
            byoc_fair_admission_max_inflight_global=fair_admission_max_inflight_global,
            byoc_fair_admission_wait_timeout_ms=fair_admission_wait_timeout_ms,
        ),
    )
    return TestClient(build_test_app(settings=settings))


def test_byoc_runtime_control_issue_claim_submit_happy_path() -> None:
    client = _byoc_client()
    ctx = client.app.state.tenant_factory.get_or_create("t1")
    adapter = ctx.tool_executor.execution_adapter()
    assert adapter is not None

    from src.schemas.tool_io import ToolCallContext
    from src.tools.registry import ToolDescriptor

    call = ToolCallContext(
        schema_version="1.0",
        call_id="api_call_1",
        session_id="sess_1",
        run_id="run_1",
        job_id="job_1",
        task_id="task_1",
        agent_id="agent_1",
        provider_id="openai-test",
        tool_name="echo_tool",
        arguments={"x": 7},
        tenant_id="t1",
    )
    descriptor = ToolDescriptor(name="echo_tool", handler=lambda x: x, timeout_ms=1500)
    result_holder: dict[str, object] = {}

    def _execute() -> None:
        result_holder["result"] = adapter.execute(call, descriptor)

    thread = threading.Thread(target=_execute)
    thread.start()

    token_resp = client.post(
        "/tenants/t1/admin/byoc/worker-token",
        json={"worker_id": "worker-a"},
        headers=_headers("t1"),
    )
    assert token_resp.status_code == 200
    token = token_resp.json()["token"]

    claim_resp = client.post(
        "/tenants/t1/admin/byoc/jobs/claim",
        json={"worker_token": token, "request_nonce": "api-claim-nonce-001"},
        headers=_headers("t1"),
    )
    assert claim_resp.status_code == 200
    job = claim_resp.json()["job"]
    assert job is not None
    assert "artifact_bundle_hash_sha256" in job
    assert "artifact_bundle_signature_hmac_sha256" in job
    assert "artifact_signature_version" in job
    submit_resp = client.post(
        "/tenants/t1/admin/byoc/jobs/submit",
        json={
            "worker_token": token,
            "result": {
                "job_id": job["job_id"],
                "tenant_id": "t1",
                "run_id": job["run_id"],
                "call_id": job["call_id"],
                "tool_name": job["tool_name"],
                "status": "success",
                "output": {"ok": True},
                "idempotency_key": job["idempotency_key"],
                "lease_token": job["lease_token"],
                "artifact_bundle_hash_sha256": "hash-api-v1",
                "artifact_bundle_signature_hmac_sha256": "sig-api-v1",
                "artifact_signature_version": "v1",
            },
            "request_nonce": "api-submit-nonce-001",
        },
        headers=_headers("t1"),
    )
    assert submit_resp.status_code == 200
    assert submit_resp.json()["accepted"] is True
    thread.join(timeout=2.0)
    assert result_holder["result"].status.value == "success"


def test_byoc_runtime_control_rejects_invalid_signature() -> None:
    client = _byoc_client()
    claim_resp = client.post(
        "/tenants/t1/admin/byoc/jobs/claim",
        json={"worker_token": "not-a-jwt", "request_nonce": "api-claim-nonce-002"},
        headers=_headers("t1"),
    )
    assert claim_resp.status_code == 401


def test_byoc_runtime_control_replayed_nonce_rejected() -> None:
    client = _byoc_client()
    token_resp = client.post(
        "/tenants/t1/admin/byoc/worker-token",
        json={"worker_id": "worker-r"},
        headers=_headers("t1"),
    )
    token = token_resp.json()["token"]
    first = client.post(
        "/tenants/t1/admin/byoc/jobs/claim",
        json={"worker_token": token, "request_nonce": "api-replay-nonce-001"},
        headers=_headers("t1"),
    )
    assert first.status_code == 200
    replay = client.post(
        "/tenants/t1/admin/byoc/jobs/claim",
        json={"worker_token": token, "request_nonce": "api-replay-nonce-001"},
        headers=_headers("t1"),
    )
    assert replay.status_code == 401
    assert replay.json()["detail"] == "WORKER_REQUEST_REPLAYED"


def test_byoc_runtime_control_duplicate_submit_reports_duplicate() -> None:
    client = _byoc_client()
    ctx = client.app.state.tenant_factory.get_or_create("t1")
    adapter = ctx.tool_executor.execution_adapter()
    assert adapter is not None
    from src.schemas.tool_io import ToolCallContext
    from src.tools.registry import ToolDescriptor

    call = ToolCallContext(
        schema_version="1.0",
        call_id="api_call_dup_1",
        session_id="sess_dup_1",
        run_id="run_dup_1",
        job_id="job_dup_1",
        task_id="task_dup_1",
        agent_id="agent_dup_1",
        provider_id="openai-test",
        tool_name="echo_tool",
        arguments={"x": 9},
        tenant_id="t1",
    )
    descriptor = ToolDescriptor(name="echo_tool", handler=lambda x: x, timeout_ms=1500)
    run_thread = threading.Thread(target=lambda: adapter.execute(call, descriptor))
    run_thread.start()

    token_resp = client.post(
        "/tenants/t1/admin/byoc/worker-token",
        json={"worker_id": "worker-dup"},
        headers=_headers("t1"),
    )
    token = token_resp.json()["token"]
    claim_resp = client.post(
        "/tenants/t1/admin/byoc/jobs/claim",
        json={"worker_token": token, "request_nonce": "api-claim-nonce-dup-001"},
        headers=_headers("t1"),
    )
    job = claim_resp.json()["job"]
    assert job is not None

    payload = {
        "job_id": job["job_id"],
        "tenant_id": "t1",
        "run_id": job["run_id"],
        "call_id": job["call_id"],
        "tool_name": job["tool_name"],
        "status": "success",
        "output": {"ok": True},
        "idempotency_key": job["idempotency_key"],
        "lease_token": job["lease_token"],
    }
    first = client.post(
        "/tenants/t1/admin/byoc/jobs/submit",
        json={
            "worker_token": token,
            "request_nonce": "api-submit-nonce-dup-001",
            "result": payload,
        },
        headers=_headers("t1"),
    )
    second = client.post(
        "/tenants/t1/admin/byoc/jobs/submit",
        json={
            "worker_token": token,
            "request_nonce": "api-submit-nonce-dup-002",
            "result": payload,
        },
        headers=_headers("t1"),
    )
    run_thread.join(timeout=2.0)
    assert first.status_code == 200
    assert first.json()["accepted"] is True
    assert first.json()["duplicate"] is False
    assert second.status_code == 200
    assert second.json()["accepted"] is True
    assert second.json()["duplicate"] is True


def test_byoc_runtime_control_submit_rejects_artifact_integrity_mismatch() -> None:
    client = _byoc_client()
    ctx = client.app.state.tenant_factory.get_or_create("t1")
    adapter = ctx.tool_executor.execution_adapter()
    assert adapter is not None
    from src.schemas.tool_io import ToolCallContext
    from src.tools.registry import ToolDescriptor

    call = ToolCallContext(
        schema_version="1.0",
        call_id="api_call_integrity_1",
        session_id="sess_integrity_1",
        run_id="run_integrity_1",
        job_id="job_integrity_1",
        task_id="task_integrity_1",
        agent_id="agent_integrity_1",
        provider_id="openai-test",
        tool_name="echo_tool",
        arguments={"x": 10},
        tenant_id="t1",
    )
    descriptor = ToolDescriptor(
        name="echo_tool",
        handler=lambda x: x,
        timeout_ms=200,
        metadata={
            "artifact_bundle_hash_sha256": "hash-expected-api",
            "artifact_bundle_signature_hmac_sha256": "sig-expected-api",
            "artifact_signature_version": "v2",
        },
    )
    run_thread = threading.Thread(target=lambda: adapter.execute(call, descriptor))
    run_thread.start()
    token_resp = client.post(
        "/tenants/t1/admin/byoc/worker-token",
        json={"worker_id": "worker-integrity-api"},
        headers=_headers("t1"),
    )
    token = token_resp.json()["token"]
    claim_resp = client.post(
        "/tenants/t1/admin/byoc/jobs/claim",
        json={"worker_token": token, "request_nonce": "api-claim-nonce-integrity-001"},
        headers=_headers("t1"),
    )
    job = claim_resp.json()["job"]
    assert job is not None
    submit_resp = client.post(
        "/tenants/t1/admin/byoc/jobs/submit",
        json={
            "worker_token": token,
            "request_nonce": "api-submit-nonce-integrity-001",
            "result": {
                "job_id": job["job_id"],
                "tenant_id": "t1",
                "run_id": job["run_id"],
                "call_id": job["call_id"],
                "tool_name": job["tool_name"],
                "status": "success",
                "output": {"ok": True},
                "idempotency_key": job["idempotency_key"],
                "lease_token": job["lease_token"],
                "artifact_bundle_hash_sha256": "hash-tampered-api",
                "artifact_bundle_signature_hmac_sha256": "sig-expected-api",
                "artifact_signature_version": "v2",
            },
        },
        headers=_headers("t1"),
    )
    assert submit_resp.status_code == 200
    assert submit_resp.json()["accepted"] is False
    assert submit_resp.json()["reason_code"] == "BYOC_ARTIFACT_INTEGRITY_MISMATCH"
    run_thread.join(timeout=1.0)


def test_byoc_runtime_control_stats_include_health_metrics_and_cleanup_endpoint() -> None:
    client = _byoc_client()
    token_resp = client.post(
        "/tenants/t1/admin/byoc/worker-token",
        json={"worker_id": "worker-health"},
        headers=_headers("t1"),
    )
    assert token_resp.status_code == 200

    stats_resp = client.get("/tenants/t1/admin/runtime/control-stats", headers=_headers("t1"))
    assert stats_resp.status_code == 200
    stats = stats_resp.json()["control_stats"]
    assert "queued_jobs" in stats
    assert "leased_jobs" in stats
    assert "pending_result_payloads" in stats
    assert "replay_keys_active" in stats
    assert "fair_admission_timeout_total" in stats

    cleanup_resp = client.post(
        "/tenants/t1/admin/byoc/cleanup",
        json={"force": True},
        headers=_headers("t1"),
    )
    assert cleanup_resp.status_code == 200
    cleanup_stats = cleanup_resp.json()["cleanup_stats"]
    assert "job_records_pruned" in cleanup_stats
    assert "result_records_pruned" in cleanup_stats
    assert "replay_records_pruned" in cleanup_stats


def test_byoc_runtime_control_stats_include_fairness_timeout_indicators_per_tenant() -> None:
    client = _byoc_client(
        fair_admission_enabled=True,
        fair_admission_max_inflight_global=1,
        fair_admission_wait_timeout_ms=40,
    )
    from src.schemas.tool_io import ToolCallContext
    from src.tools.registry import ToolDescriptor

    ctx_t1 = client.app.state.tenant_factory.get_or_create("t1")
    ctx_t2 = client.app.state.tenant_factory.get_or_create("t2")
    adapter_t1 = ctx_t1.tool_executor.execution_adapter()
    adapter_t2 = ctx_t2.tool_executor.execution_adapter()
    assert adapter_t1 is not None
    assert adapter_t2 is not None

    call_t1 = ToolCallContext(
        schema_version="1.0",
        call_id="fairness_t1_call",
        session_id="sess_fair_t1",
        run_id="run_fair_t1",
        job_id="job_fair_t1",
        task_id="task_fair_t1",
        agent_id="agent_fair_t1",
        provider_id="openai-test",
        tool_name="echo_tool",
        arguments={"x": 1},
        tenant_id="t1",
    )
    call_t2 = ToolCallContext(
        schema_version="1.0",
        call_id="fairness_t2_call",
        session_id="sess_fair_t2",
        run_id="run_fair_t2",
        job_id="job_fair_t2",
        task_id="task_fair_t2",
        agent_id="agent_fair_t2",
        provider_id="openai-test",
        tool_name="echo_tool",
        arguments={"x": 2},
        tenant_id="t2",
    )
    descriptor = ToolDescriptor(name="echo_tool", handler=lambda x: x, timeout_ms=400)
    holder: dict[str, object] = {}
    t1_thread = threading.Thread(target=lambda: holder.setdefault("t1", adapter_t1.execute(call_t1, descriptor)))
    t1_thread.start()
    timeout_result = adapter_t2.execute(call_t2, descriptor)
    t1_thread.join(timeout=1.0)

    assert timeout_result.status.value == "error"
    assert timeout_result.error.code == "BYOC_FAIR_ADMISSION_TIMEOUT"

    stats_resp = client.get("/tenants/t2/admin/runtime/control-stats", headers=_headers("t2"))
    assert stats_resp.status_code == 200
    stats = stats_resp.json()["control_stats"]
    assert stats["fair_admission_enabled"] == 1
    assert stats["fair_admission_wait_timeout_ms"] == 40
    assert stats["fair_admission_timeout_total"] >= 1
    assert stats["tenant_fair_admission_timeout_total"] >= 1
    assert stats["tenant_rejected_reason_BYOC_FAIR_ADMISSION_TIMEOUT"] >= 1


def test_byoc_webhook_submit_happy_path_and_auth_failure() -> None:
    client = _byoc_client()
    ctx = client.app.state.tenant_factory.get_or_create("t1")
    adapter = ctx.tool_executor.execution_adapter()
    assert adapter is not None
    from src.schemas.tool_io import ToolCallContext
    from src.tools.registry import ToolDescriptor

    call = ToolCallContext(
        schema_version="1.0",
        call_id="api_call_webhook_1",
        session_id="sess_webhook_1",
        run_id="run_webhook_1",
        job_id="job_webhook_1",
        task_id="task_webhook_1",
        agent_id="agent_webhook_1",
        provider_id="openai-test",
        tool_name="echo_tool",
        arguments={"x": 3},
        tenant_id="t1",
    )
    descriptor = ToolDescriptor(name="echo_tool", handler=lambda x: x, timeout_ms=1500)
    run_thread = threading.Thread(target=lambda: adapter.execute(call, descriptor))
    run_thread.start()

    token_resp = client.post(
        "/tenants/t1/admin/byoc/worker-token",
        json={"worker_id": "worker-webhook"},
        headers=_headers("t1"),
    )
    token = token_resp.json()["token"]
    claim_resp = client.post(
        "/tenants/t1/admin/byoc/jobs/claim",
        json={"worker_token": token, "request_nonce": "api-claim-nonce-webhook-001"},
        headers=_headers("t1"),
    )
    job = claim_resp.json()["job"]
    assert job is not None

    bad_resp = client.post(
        "/tenants/t1/admin/byoc/webhook/jobs/submit",
        json={
            "webhook_secret": "wrong-secret",
            "webhook_request_id": "api-webhook-rid-001",
            "result": {
                "job_id": job["job_id"],
                "tenant_id": "t1",
                "run_id": job["run_id"],
                "call_id": job["call_id"],
                "tool_name": job["tool_name"],
                "status": "success",
                "output": {"ok": True},
                "idempotency_key": job["idempotency_key"],
                "lease_token": job["lease_token"],
            },
        },
        headers=_headers("t1"),
    )
    assert bad_resp.status_code == 401
    assert bad_resp.json()["detail"] == "WEBHOOK_AUTH_INVALID"

    good_resp = client.post(
        "/tenants/t1/admin/byoc/webhook/jobs/submit",
        json={
            "webhook_secret": "test-secret",
            "webhook_request_id": "api-webhook-rid-002",
            "result": {
                "job_id": job["job_id"],
                "tenant_id": "t1",
                "run_id": job["run_id"],
                "call_id": job["call_id"],
                "tool_name": job["tool_name"],
                "status": "success",
                "output": {"ok": True},
                "idempotency_key": job["idempotency_key"],
                "lease_token": job["lease_token"],
            },
        },
        headers=_headers("t1"),
    )
    assert good_resp.status_code == 200
    assert good_resp.json()["accepted"] is True
    run_thread.join(timeout=2.0)


def test_byoc_dlq_list_and_replay_api_flow() -> None:
    client = _byoc_client(max_claim_attempts_before_dlq=1, lease_ttl_seconds=1)
    ctx = client.app.state.tenant_factory.get_or_create("t1")
    adapter = ctx.tool_executor.execution_adapter()
    assert adapter is not None
    from src.schemas.tool_io import ToolCallContext
    from src.tools.registry import ToolDescriptor
    import time

    call = ToolCallContext(
        schema_version="1.0",
        call_id="api_call_dlq_1",
        session_id="sess_dlq_1",
        run_id="run_dlq_1",
        job_id="job_dlq_1",
        task_id="task_dlq_1",
        agent_id="agent_dlq_1",
        provider_id="openai-test",
        tool_name="echo_tool",
        arguments={"x": 5},
        tenant_id="t1",
    )
    descriptor = ToolDescriptor(name="echo_tool", handler=lambda x: x, timeout_ms=2500)
    result_holder: dict[str, object] = {}

    run_thread = threading.Thread(target=lambda: result_holder.setdefault("result", adapter.execute(call, descriptor)))
    run_thread.start()

    token_resp = client.post(
        "/tenants/t1/admin/byoc/worker-token",
        json={"worker_id": "worker-dlq-api"},
        headers=_headers("t1"),
    )
    token = token_resp.json()["token"]
    claim_resp = client.post(
        "/tenants/t1/admin/byoc/jobs/claim",
        json={"worker_token": token, "request_nonce": "api-claim-nonce-dlq-001"},
        headers=_headers("t1"),
    )
    job = claim_resp.json()["job"]
    assert job is not None
    time.sleep(1.2)

    _ = client.post(
        "/tenants/t1/admin/byoc/jobs/claim",
        json={"worker_token": token, "request_nonce": "api-claim-nonce-dlq-002"},
        headers=_headers("t1"),
    )

    dlq_resp = client.get("/tenants/t1/admin/byoc/dlq?limit=10", headers=_headers("t1"))
    assert dlq_resp.status_code == 200
    records = dlq_resp.json()["records"]
    assert len(records) == 1
    assert records[0]["job_id"] == job["job_id"]
    assert records[0]["dead_letter_reason_code"] == "BYOC_LEASE_RETRY_EXHAUSTED"

    replay_resp = client.post(
        f"/tenants/t1/admin/byoc/dlq/{job['job_id']}/replay",
        headers=_headers("t1"),
    )
    assert replay_resp.status_code == 200
    assert replay_resp.json()["replayed"] is True

    replay_claim = client.post(
        "/tenants/t1/admin/byoc/jobs/claim",
        json={"worker_token": token, "request_nonce": "api-claim-nonce-dlq-003"},
        headers=_headers("t1"),
    )
    replay_job = replay_claim.json()["job"]
    assert replay_job is not None
    assert replay_job["job_id"] == job["job_id"]

    submit_resp = client.post(
        "/tenants/t1/admin/byoc/jobs/submit",
        json={
            "worker_token": token,
            "request_nonce": "api-submit-nonce-dlq-001",
            "result": {
                "job_id": replay_job["job_id"],
                "tenant_id": "t1",
                "run_id": replay_job["run_id"],
                "call_id": replay_job["call_id"],
                "tool_name": replay_job["tool_name"],
                "status": "success",
                "output": {"ok": True},
                "idempotency_key": replay_job["idempotency_key"],
                "lease_token": replay_job["lease_token"],
            },
        },
        headers=_headers("t1"),
    )
    assert submit_resp.status_code == 200
    assert submit_resp.json()["accepted"] is True
    run_thread.join(timeout=2.0)


def test_byoc_governance_metrics_export_contract_includes_reason_rollup() -> None:
    client = _byoc_client()
    token_resp = client.post(
        "/tenants/t1/admin/byoc/worker-token",
        json={"worker_id": "worker-governance"},
        headers=_headers("t1"),
    )
    assert token_resp.status_code == 200
    token = token_resp.json()["token"]

    reject_resp = client.post(
        "/tenants/t1/admin/byoc/jobs/submit",
        json={
            "worker_token": token,
            "request_nonce": "api-submit-nonce-governance-001",
            "result": {
                "job_id": "missing-job",
                "tenant_id": "t1",
                "run_id": "run-missing",
                "call_id": "call-missing",
                "tool_name": "echo_tool",
                "status": "error",
                "output": {},
                "idempotency_key": "gov-idempotency-1",
                "lease_token": "bad-lease",
            },
        },
        headers=_headers("t1"),
    )
    assert reject_resp.status_code == 200
    assert reject_resp.json()["accepted"] is False

    metrics_resp = client.get(
        "/tenants/t1/admin/byoc/governance-metrics",
        headers=_headers("t1"),
    )
    assert metrics_resp.status_code == 200
    payload = metrics_resp.json()
    assert payload["tenant_id"] == "t1"
    assert payload["backend_id"] == "byoc_pull_worker_runtime"
    assert payload["cost"]["window"] == "lifetime"
    assert payload["submissions"]["window"] == "lifetime"
    assert payload["submissions"]["submit_attempts_total"] >= 1
    assert payload["submissions"]["rejected_results_total"] >= 1
    assert 0.0 <= payload["submissions"]["rejection_rate"] <= 1.0
    assert payload["anomaly_report"]["enabled"] is True
    assert payload["anomaly_report"]["advisory_only"] is True
    reason_codes = {item["reason_code"] for item in payload["rejection_reasons"]}
    assert "BYOC_LEASE_INVALID_OR_EXPIRED" in reason_codes


def test_byoc_governance_metrics_export_uses_windowed_cost_fields_when_enabled() -> None:
    client = _byoc_client(enable_cost_window_policy=True, cost_window_seconds=120)
    metrics_resp = client.get(
        "/tenants/t1/admin/byoc/governance-metrics",
        headers=_headers("t1"),
    )
    assert metrics_resp.status_code == 200
    payload = metrics_resp.json()
    assert payload["cost"]["window"] == "windowed"
    assert payload["cost"]["window_seconds"] == 120
    assert payload["cost"]["window_started_at_epoch"] >= 0


def test_byoc_governance_metrics_export_includes_anomaly_findings_when_threshold_exceeded() -> None:
    client = _byoc_client(
        anomaly_rejection_rate_threshold=0.5,
        anomaly_min_submit_attempts=1,
        anomaly_min_rejection_count=1,
    )
    token_resp = client.post(
        "/tenants/t1/admin/byoc/worker-token",
        json={"worker_id": "worker-anomaly"},
        headers=_headers("t1"),
    )
    token = token_resp.json()["token"]
    reject_resp = client.post(
        "/tenants/t1/admin/byoc/jobs/submit",
        json={
            "worker_token": token,
            "request_nonce": "api-submit-nonce-anomaly-001",
            "result": {
                "job_id": "missing-job",
                "tenant_id": "t1",
                "run_id": "run-missing",
                "call_id": "call-missing",
                "tool_name": "echo_tool",
                "status": "error",
                "output": {},
                "idempotency_key": "gov-anomaly-idempotency",
                "lease_token": "bad-lease",
            },
        },
        headers=_headers("t1"),
    )
    assert reject_resp.status_code == 200
    assert reject_resp.json()["accepted"] is False

    metrics_resp = client.get("/tenants/t1/admin/byoc/governance-metrics", headers=_headers("t1"))
    payload = metrics_resp.json()
    codes = {item["code"] for item in payload["anomaly_report"]["anomalies"]}
    assert "BYOC_REJECTION_RATE_SPIKE" in codes

