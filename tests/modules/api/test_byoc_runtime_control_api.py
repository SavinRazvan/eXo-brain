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

import asyncio
import json
import threading
from typing import cast

from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.constants import BYOC_WORKER_JWT_SECRET

from src.api.bootstrap import build_test_app
from src.config.settings import AppSettings, RuntimeSettings
from src.schemas.tool_io import ToolResult, ToolStatus


def _fastapi_app(client: TestClient) -> FastAPI:
    """TestClient.app is typed as a generic ASGI wrapper; tests always use FastAPI."""
    return cast(FastAPI, client.app)


def _headers(tenant_id: str = "t1", roles: list[str] | None = None) -> dict[str, str]:
    payload = {
        "subject": "admin@test.com",
        "roles": roles or ["admin", "entitlement_pro"],
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
    budget_partition_scope: str = "tenant",
    budget_partition_limits_microunits: dict[str, int] | None = None,
    enforce_cost_limit: bool = False,
    cost_limit_microunits_per_tenant: int = 1_000_000,
    cost_success_microunits: int = 100,
    cost_error_microunits: int = 40,
    cost_timeout_microunits: int = 60,
    cost_cancelled_microunits: int = 20,
) -> TestClient:
    settings = AppSettings(
        schema_version="1.0",
        environment="test",
        runtime=RuntimeSettings(
            default_provider_id="openai-test",
            allowed_provider_ids=["openai-test"],
            require_provider_healthcheck_on_start=False,
            enable_byoc_tool_runtime=True,
            byoc_worker_jwt_secret=BYOC_WORKER_JWT_SECRET,
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
            byoc_budget_partition_scope=budget_partition_scope,
            byoc_budget_partition_limits_microunits=budget_partition_limits_microunits or {},
            byoc_enforce_cost_limit=enforce_cost_limit,
            byoc_cost_limit_microunits_per_tenant=cost_limit_microunits_per_tenant,
            byoc_cost_success_microunits=cost_success_microunits,
            byoc_cost_error_microunits=cost_error_microunits,
            byoc_cost_timeout_microunits=cost_timeout_microunits,
            byoc_cost_cancelled_microunits=cost_cancelled_microunits,
        ),
    )
    return TestClient(build_test_app(settings=settings))


def test_byoc_runtime_control_issue_claim_submit_happy_path() -> None:
    client = _byoc_client()
    ctx = _fastapi_app(client).state.tenant_factory.get_or_create("t1")
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
    result_holder: dict[str, ToolResult] = {}

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
    assert result_holder["result"].status == ToolStatus.SUCCESS


def test_byoc_governance_metrics_requires_pro_entitlement_and_emits_audit() -> None:
    client = _byoc_client()
    app = _fastapi_app(client)
    resp = client.get(
        "/tenants/t1/admin/byoc/governance-metrics",
        headers=_headers("t1", roles=["admin"]),
    )
    assert resp.status_code == 403
    assert "ENTITLEMENT_TIER_REQUIRED" in resp.text

    records = asyncio.run(app.state.audit_store.list_audit_events(tenant_id="t1", limit=20))
    entitlement = [record for record in records if record.event_type == "entitlement_decision"]
    assert entitlement
    latest = entitlement[-1]
    assert latest.payload.get("surface") == "byoc_governance_metrics"
    assert latest.payload.get("feature") == "governance.byoc.governance_analytics"
    assert latest.payload.get("decision") == "deny"
    assert latest.payload.get("required_tier") == "pro"


def test_byoc_runtime_control_rejects_invalid_signature() -> None:
    client = _byoc_client()
    claim_resp = client.post(
        "/tenants/t1/admin/byoc/jobs/claim",
        json={"worker_token": "not-a-jwt", "request_nonce": "api-claim-nonce-002"},
        headers=_headers("t1"),
    )
    assert claim_resp.status_code == 401


def test_byoc_submit_result_rejects_invalid_worker_token() -> None:
    client = _byoc_client()
    resp = client.post(
        "/tenants/t1/admin/byoc/jobs/submit",
        json={
            "worker_token": "totally-not-a-jwt",
            "request_nonce": "abcdefgh",
            "result": {
                "job_id": "job-x",
                "tenant_id": "t1",
                "run_id": "run-x",
                "call_id": "call-x",
                "tool_name": "echo_tool",
            },
        },
        headers=_headers("t1"),
    )
    assert resp.status_code == 401


def test_byoc_admin_routes_return_409_when_only_hosted_runtime_enabled() -> None:
    settings = AppSettings(
        schema_version="1.0",
        environment="test",
        runtime=RuntimeSettings(
            default_provider_id="openai-test",
            allowed_provider_ids=["openai-test"],
            require_provider_healthcheck_on_start=False,
            enable_hosted_tool_runtime=True,
            enable_byoc_tool_runtime=False,
        ),
    )
    client = TestClient(build_test_app(settings=settings))
    resp = client.post(
        "/tenants/t1/admin/byoc/jobs/submit",
        json={
            "worker_token": "x",
            "request_nonce": "12345678",
            "result": {"job_id": "j", "tenant_id": "t1", "run_id": "r", "call_id": "c", "tool_name": "t"},
        },
        headers=_headers("t1"),
    )
    assert resp.status_code == 409
    assert "BYOC" in resp.json()["detail"]


def test_byoc_dlq_bulk_replay_ingests_partial_failure_summary() -> None:
    client = _byoc_client()
    ctx = _fastapi_app(client).state.tenant_factory.get_or_create("t1")
    adapter = ctx.tool_executor.execution_adapter()
    assert adapter is not None

    def _fake_bulk(*, tenant_id: str, job_ids: list[str], limit: int) -> dict:  # noqa: ARG001
        return {
            "attempted": 3,
            "replayed": 1,
            "failures": [
                "not-a-dict",
                {"job_id": "", "reason_code": "IGNORED"},
                {"job_id": "job-bad", "reason_code": ""},
            ],
        }

    adapter.replay_dead_letter_jobs = _fake_bulk  # type: ignore[assignment]
    resp = client.post(
        "/tenants/t1/admin/byoc/dlq/replay",
        json={"job_ids": ["job-a", "job-b"], "limit": 10},
        headers=_headers("t1"),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["attempted"] == 3
    assert body["replayed"] == 1
    assert body["failures"] == [{"job_id": "job-bad", "reason_code": "DLQ_REPLAY_REJECTED"}]


def test_byoc_dlq_bulk_replay_falls_back_to_single_replay_when_bulk_missing() -> None:
    client = _byoc_client()
    ctx = _fastapi_app(client).state.tenant_factory.get_or_create("t1")
    adapter = ctx.tool_executor.execution_adapter()
    assert adapter is not None
    adapter.replay_dead_letter_jobs = None  # type: ignore[assignment]

    def _replay_one(*, tenant_id: str, job_id: str) -> bool:  # noqa: ARG001
        return job_id == "job-ok"

    adapter.replay_dead_letter_job = _replay_one  # type: ignore[method-assign]

    resp = client.post(
        "/tenants/t1/admin/byoc/dlq/replay",
        json={"job_ids": ["job-ok", "job-miss"], "limit": 10},
        headers=_headers("t1"),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["attempted"] == 2
    assert body["replayed"] == 1
    assert len(body["failures"]) == 1
    assert body["failures"][0]["job_id"] == "job-miss"


def test_byoc_dlq_bulk_replay_returns_empty_summary_when_no_job_ids_resolved() -> None:
    client = _byoc_client()
    ctx = _fastapi_app(client).state.tenant_factory.get_or_create("t1")
    adapter = ctx.tool_executor.execution_adapter()
    assert adapter is not None

    def _empty_dlq(*, tenant_id: str, limit: int) -> list[dict[str, str]]:  # noqa: ARG001
        return []

    adapter.list_dead_letter_jobs = _empty_dlq  # type: ignore[method-assign]
    adapter.replay_dead_letter_jobs = None  # type: ignore[assignment]
    adapter.replay_dead_letter_job = lambda **kwargs: False  # type: ignore[assignment]

    resp = client.post(
        "/tenants/t1/admin/byoc/dlq/replay",
        json={"job_ids": [], "limit": 5},
        headers=_headers("t1"),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["attempted"] == 0
    assert body["replayed"] == 0
    assert body["failures"] == []


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
    ctx = _fastapi_app(client).state.tenant_factory.get_or_create("t1")
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
    ctx = _fastapi_app(client).state.tenant_factory.get_or_create("t1")
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

    ctx_t1 = _fastapi_app(client).state.tenant_factory.get_or_create("t1")
    ctx_t2 = _fastapi_app(client).state.tenant_factory.get_or_create("t2")
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
    ctx = _fastapi_app(client).state.tenant_factory.get_or_create("t1")
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
            "webhook_secret": BYOC_WORKER_JWT_SECRET,
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
    ctx = _fastapi_app(client).state.tenant_factory.get_or_create("t1")
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


def test_byoc_dlq_bulk_replay_returns_deterministic_summary() -> None:
    client = _byoc_client(max_claim_attempts_before_dlq=1, lease_ttl_seconds=1)
    ctx = _fastapi_app(client).state.tenant_factory.get_or_create("t1")
    adapter = ctx.tool_executor.execution_adapter()
    assert adapter is not None
    from src.schemas.tool_io import ToolCallContext
    from src.tools.registry import ToolDescriptor
    import time

    descriptor = ToolDescriptor(name="echo_tool", handler=lambda x: x, timeout_ms=2500)
    threads: list[threading.Thread] = []
    for idx in range(2):
        call = ToolCallContext(
            schema_version="1.0",
            call_id=f"api_call_dlq_bulk_{idx}",
            session_id=f"sess_dlq_bulk_{idx}",
            run_id=f"run_dlq_bulk_{idx}",
            job_id=f"job_dlq_bulk_{idx}",
            task_id=f"task_dlq_bulk_{idx}",
            agent_id=f"agent_dlq_bulk_{idx}",
            provider_id="openai-test",
            tool_name="echo_tool",
            arguments={"x": idx},
            tenant_id="t1",
        )
        thread = threading.Thread(target=lambda c=call: adapter.execute(c, descriptor))
        thread.start()
        threads.append(thread)

    token_resp = client.post(
        "/tenants/t1/admin/byoc/worker-token",
        json={"worker_id": "worker-dlq-bulk-api"},
        headers=_headers("t1"),
    )
    token = token_resp.json()["token"]
    for nonce_idx in range(2):
        claim_resp = client.post(
            "/tenants/t1/admin/byoc/jobs/claim",
            json={"worker_token": token, "request_nonce": f"api-claim-nonce-dlq-bulk-{nonce_idx}"},
            headers=_headers("t1"),
        )
        assert claim_resp.status_code == 200
        assert claim_resp.json()["job"] is not None
    time.sleep(1.2)
    _ = client.post(
        "/tenants/t1/admin/byoc/jobs/claim",
        json={"worker_token": token, "request_nonce": "api-claim-nonce-dlq-bulk-refresh"},
        headers=_headers("t1"),
    )

    dlq_resp = client.get("/tenants/t1/admin/byoc/dlq?limit=10", headers=_headers("t1"))
    records = dlq_resp.json()["records"]
    assert len(records) >= 2
    first_job_id = records[0]["job_id"]
    second_job_id = records[1]["job_id"]

    replay_resp = client.post(
        "/tenants/t1/admin/byoc/dlq/replay",
        json={
            "job_ids": [first_job_id, second_job_id, "missing-job-id"],
            "limit": 10,
        },
        headers=_headers("t1"),
    )
    assert replay_resp.status_code == 200
    payload = replay_resp.json()
    assert payload["attempted"] == 3
    assert payload["replayed"] == 2
    assert payload["failed"] == 1
    assert payload["failures"] == [
        {
            "job_id": "missing-job-id",
            "reason_code": "DLQ_REPLAY_NOT_FOUND_OR_NOT_DLQ",
        }
    ]
    for thread in threads:
        thread.join(timeout=3.0)


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


def test_byoc_provider_partition_cost_limit_is_tenant_isolated() -> None:
    client = _byoc_client(
        enable_cost_window_policy=True,
        cost_window_seconds=120,
        enforce_cost_limit=True,
        cost_limit_microunits_per_tenant=100,
        cost_success_microunits=2,
        budget_partition_scope="per_provider",
        budget_partition_limits_microunits={"provider:openai-test": 2},
    )

    from src.schemas.tool_io import ToolCallContext
    from src.tools.registry import ToolDescriptor

    descriptor = ToolDescriptor(name="echo_tool", handler=lambda x: x, timeout_ms=1500)

    def _execute_success(tenant_id: str, call_suffix: str) -> None:
        ctx = _fastapi_app(client).state.tenant_factory.get_or_create(tenant_id)
        adapter = ctx.tool_executor.execution_adapter()
        assert adapter is not None
        call = ToolCallContext(
            schema_version="1.0",
            call_id=f"partition_call_{tenant_id}_{call_suffix}",
            session_id=f"partition_sess_{tenant_id}",
            run_id=f"partition_run_{tenant_id}_{call_suffix}",
            job_id=f"partition_job_{tenant_id}_{call_suffix}",
            task_id=f"partition_task_{tenant_id}_{call_suffix}",
            agent_id="partition_agent",
            provider_id="openai-test",
            tool_name="echo_tool",
            arguments={"x": 1},
            tenant_id=tenant_id,
        )
        result_holder: dict[str, ToolResult] = {}
        thread = threading.Thread(target=lambda: result_holder.setdefault("result", adapter.execute(call, descriptor)))
        thread.start()
        token_resp = client.post(
            f"/tenants/{tenant_id}/admin/byoc/worker-token",
            json={"worker_id": f"worker-{tenant_id}"},
            headers=_headers(tenant_id),
        )
        token = token_resp.json()["token"]
        claim_resp = client.post(
            f"/tenants/{tenant_id}/admin/byoc/jobs/claim",
            json={"worker_token": token, "request_nonce": f"partition-claim-{tenant_id}-{call_suffix}"},
            headers=_headers(tenant_id),
        )
        job = claim_resp.json()["job"]
        assert job is not None
        submit_resp = client.post(
            f"/tenants/{tenant_id}/admin/byoc/jobs/submit",
            json={
                "worker_token": token,
                "request_nonce": f"partition-submit-{tenant_id}-{call_suffix}",
                "result": {
                    "job_id": job["job_id"],
                    "tenant_id": tenant_id,
                    "run_id": job["run_id"],
                    "call_id": job["call_id"],
                    "tool_name": job["tool_name"],
                    "status": "success",
                    "output": {"ok": True},
                    "idempotency_key": job["idempotency_key"],
                    "lease_token": job["lease_token"],
                },
            },
            headers=_headers(tenant_id),
        )
        assert submit_resp.status_code == 200
        assert submit_resp.json()["accepted"] is True
        thread.join(timeout=2.0)
        assert result_holder["result"].status == ToolStatus.SUCCESS

    _execute_success("t1", "1")

    t1_ctx = _fastapi_app(client).state.tenant_factory.get_or_create("t1")
    t1_adapter = t1_ctx.tool_executor.execution_adapter()
    assert t1_adapter is not None
    blocked_call = ToolCallContext(
        schema_version="1.0",
        call_id="partition_call_t1_blocked",
        session_id="partition_sess_t1",
        run_id="partition_run_t1_blocked",
        job_id="partition_job_t1_blocked",
        task_id="partition_task_t1_blocked",
        agent_id="partition_agent",
        provider_id="openai-test",
        tool_name="echo_tool",
        arguments={"x": 2},
        tenant_id="t1",
    )
    blocked = t1_adapter.execute(blocked_call, descriptor)
    assert blocked.status.value == "error"
    assert blocked.error.code == "BYOC_COST_WINDOW_PARTITION_LIMIT_EXCEEDED"

    _execute_success("t2", "1")

    t1_stats = client.get("/tenants/t1/admin/runtime/control-stats", headers=_headers("t1")).json()["control_stats"]
    t2_stats = client.get("/tenants/t2/admin/runtime/control-stats", headers=_headers("t2")).json()["control_stats"]
    assert t1_stats["tenant_rejected_reason_BYOC_COST_WINDOW_PARTITION_LIMIT_EXCEEDED"] >= 1
    assert t2_stats.get("tenant_rejected_reason_BYOC_COST_WINDOW_PARTITION_LIMIT_EXCEEDED", 0) == 0


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


def test_byoc_governance_metrics_export_includes_conflict_counts() -> None:
    client = _byoc_client()
    ctx = _fastapi_app(client).state.tenant_factory.get_or_create("t1")
    adapter = ctx.tool_executor.execution_adapter()
    assert adapter is not None

    from src.tools.byoc.job_contracts import ByocResultStatus, ByocToolResultEnvelope
    from src.tools.byoc.result_store import InMemoryByocResultStore

    store = getattr(adapter, "_result_store", None)
    assert isinstance(store, InMemoryByocResultStore)
    first = ByocToolResultEnvelope(
        job_id="conflict-job-1",
        tenant_id="t1",
        run_id="run_conflict_1",
        call_id="call_conflict_1",
        tool_name="echo_tool",
        status=ByocResultStatus.ERROR,
        output={"value": 1},
        idempotency_key="t1:conflict:1",
        lease_token="lease-1",
        tool_version="v1",
    )
    second = ByocToolResultEnvelope(
        job_id="conflict-job-1",
        tenant_id="t1",
        run_id="run_conflict_1",
        call_id="call_conflict_1",
        tool_name="echo_tool",
        status=ByocResultStatus.SUCCESS,
        output={"value": 2},
        idempotency_key="t1:conflict:2",
        lease_token="lease-1",
        tool_version="v1",
    )
    _ = store.ingest(first)
    _ = store.ingest(second)

    metrics_resp = client.get("/tenants/t1/admin/byoc/governance-metrics", headers=_headers("t1"))
    assert metrics_resp.status_code == 200
    payload = metrics_resp.json()
    assert "conflict_counts" in payload
    assert payload["conflict_counts"] != []
    first_conflict = payload["conflict_counts"][0]
    assert first_conflict["strategy"] == "first_write_wins"
    assert first_conflict["tool_name"] == "echo_tool"
    assert first_conflict["tool_version"] in {"", "v1"}
    assert first_conflict["reason_code"] == "BYOC_RESULT_CONFLICT_REJECTED"

