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


def _byoc_client() -> TestClient:
    settings = AppSettings(
        schema_version="1.0",
        environment="test",
        runtime=RuntimeSettings(
            default_provider_id="openai-test",
            allowed_provider_ids=["openai-test"],
            require_provider_healthcheck_on_start=False,
            enable_byoc_tool_runtime=True,
            byoc_worker_jwt_secret="test-secret",
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

