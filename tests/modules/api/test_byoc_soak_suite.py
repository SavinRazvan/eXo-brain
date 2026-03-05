"""
File: test_byoc_soak_suite.py
Path: tests/modules/api/test_byoc_soak_suite.py
Role: Non-blocking long-run BYOC multi-tenant soak scenarios for fairness/governance regression detection.
Used By:
 - pytest (opt-in soak marker)
Depends On:
 - src/api/bootstrap.py
 - src/config/settings.py
 - src/tools/byoc/connector_runtime.py
Notes:
 - Gated behind EXO_RUN_SOAK_TESTS to keep default CI fast and deterministic.
"""

from __future__ import annotations

import json
import os
import threading
import time

import pytest
from fastapi.testclient import TestClient

from src.api.bootstrap import build_test_app
from src.config.settings import AppSettings, RuntimeSettings
from src.schemas.tool_io import ToolCallContext, ToolStatus
from src.tools.byoc.job_contracts import ByocResultStatus, ByocToolResultEnvelope
from src.tools.registry import ToolDescriptor


def _headers(tenant_id: str) -> dict[str, str]:
    payload = {
        "subject": "soak-admin@test.com",
        "roles": ["admin"],
        "tenant_id": tenant_id,
        "token_validation_state": "valid",
    }
    return {"X-Identity": json.dumps(payload)}


def _runtime_settings() -> RuntimeSettings:
    return RuntimeSettings(
        default_provider_id="openai-test",
        allowed_provider_ids=["openai-test"],
        require_provider_healthcheck_on_start=False,
        enable_byoc_tool_runtime=True,
        byoc_worker_jwt_secret="soak-secret",
        byoc_lease_ttl_seconds=5,
        byoc_enable_cost_window_policy=True,
        byoc_cost_window_seconds=2,
        byoc_cost_limit_microunits_per_tenant=40,
        byoc_enforce_cost_limit=True,
        byoc_cost_success_microunits=5,
        byoc_cost_error_microunits=2,
        byoc_cost_timeout_microunits=3,
        byoc_cost_cancelled_microunits=1,
        byoc_fair_admission_enabled=True,
        byoc_fair_admission_max_inflight_global=1,
        byoc_fair_admission_wait_timeout_ms=50,
        byoc_anomaly_detection_enabled=True,
        byoc_anomaly_rejection_rate_threshold=0.25,
        byoc_anomaly_min_submit_attempts=5,
        byoc_anomaly_min_rejection_count=3,
    )


def _call(tenant_id: str, index: int) -> ToolCallContext:
    return ToolCallContext(
        schema_version="1.0",
        call_id=f"soak_call_{tenant_id}_{index}",
        session_id=f"soak_sess_{tenant_id}",
        run_id=f"soak_run_{tenant_id}_{index}",
        job_id=f"soak_job_{tenant_id}_{index}",
        task_id=f"soak_task_{tenant_id}_{index}",
        agent_id="soak_agent",
        provider_id="openai-test",
        tool_name="echo_tool",
        arguments={"value": index, "tenant": tenant_id},
        tenant_id=tenant_id,
    )


def _wait_claim(runtime, tenant_id: str, token: str, nonce_prefix: str, timeout_s: float = 2.0) -> dict | None:
    deadline = time.time() + timeout_s
    attempt = 0
    while time.time() < deadline:
        attempt += 1
        claim = runtime.claim_next_job(
            tenant_id=tenant_id,
            worker_token=token,
            request_nonce=f"{nonce_prefix}-{attempt}",
        )
        if claim is not None:
            return claim
        time.sleep(0.01)
    return None


@pytest.mark.module_unknown
@pytest.mark.soak
@pytest.mark.skipif(
    os.getenv("EXO_RUN_SOAK_TESTS", "").strip().lower() not in {"1", "true", "yes", "on"},
    reason="Set EXO_RUN_SOAK_TESTS=true to run non-blocking soak scenarios.",
)
def test_byoc_soak_multi_tenant_budget_fairness_anomaly_signals() -> None:
    app = build_test_app(
        settings=AppSettings(
            schema_version="1.0",
            environment="test",
            runtime=_runtime_settings(),
        )
    )
    client = TestClient(app)
    tenants = ["t1", "t2", "t3"]
    descriptor = ToolDescriptor(name="echo_tool", handler=lambda value: value, timeout_ms=900)

    runtimes = {}
    tokens = {}
    done_flags = {tenant: threading.Event() for tenant in tenants}
    worker_threads: list[threading.Thread] = []
    statuses: dict[str, list[ToolStatus]] = {tenant: [] for tenant in tenants}

    for tenant in tenants:
        ctx = client.app.state.tenant_factory.get_or_create(tenant)
        runtime = ctx.tool_executor.execution_adapter()
        assert runtime is not None
        runtimes[tenant] = runtime
        token_resp = client.post(
            f"/tenants/{tenant}/admin/byoc/worker-token",
            json={"worker_id": f"soak-worker-{tenant}"},
            headers=_headers(tenant),
        )
        assert token_resp.status_code == 200
        tokens[tenant] = token_resp.json()["token"]

    def _worker_loop(tenant_id: str) -> None:
        runtime = runtimes[tenant_id]
        token = tokens[tenant_id]
        while True:
            claim = runtime.claim_next_job(
                tenant_id=tenant_id,
                worker_token=token,
                request_nonce=f"soak-claim-{tenant_id}-{int(time.time() * 1000)}",
            )
            if claim is None:
                if done_flags[tenant_id].is_set():
                    stats = runtime.control_stats_for_tenant(tenant_id=tenant_id)
                    if int(stats.get("queued_jobs", 0)) == 0 and int(stats.get("leased_jobs", 0)) == 0:
                        return
                time.sleep(0.01)
                continue
            # Small delay keeps fair-admission contention realistic and repeatable.
            time.sleep(0.04)
            runtime.submit_result(
                tenant_id=tenant_id,
                worker_token=token,
                request_nonce=f"soak-submit-{tenant_id}-{claim['job_id']}",
                result=ByocToolResultEnvelope(
                    job_id=str(claim["job_id"]),
                    tenant_id=tenant_id,
                    run_id=str(claim["run_id"]),
                    call_id=str(claim["call_id"]),
                    tool_name=str(claim["tool_name"]),
                    status=ByocResultStatus.SUCCESS,
                    output={"ok": True, "tenant": tenant_id},
                    idempotency_key=str(claim["idempotency_key"]),
                    lease_token=str(claim["lease_token"]),
                ),
            )

    for tenant in tenants:
        thread = threading.Thread(target=_worker_loop, args=(tenant,))
        worker_threads.append(thread)
        thread.start()

    for batch in range(18):
        producers: list[threading.Thread] = []
        ordered_tenants = tenants[batch % len(tenants) :] + tenants[: batch % len(tenants)]
        for tenant in ordered_tenants:
            runtime = runtimes[tenant]

            def _run_one(selected_tenant: str = tenant, index: int = batch) -> None:
                result = runtimes[selected_tenant].execute(_call(selected_tenant, index), descriptor)
                statuses[selected_tenant].append(result.status)

            t = threading.Thread(target=_run_one)
            producers.append(t)
            t.start()
        for t in producers:
            t.join(timeout=3.0)
            assert not t.is_alive()

    for tenant in tenants:
        done_flags[tenant].set()
    for thread in worker_threads:
        thread.join(timeout=3.0)
        assert not thread.is_alive()

    # No tenant starvation: every tenant must obtain at least one successful execution.
    for tenant in tenants:
        success_count = sum(1 for status in statuses[tenant] if status == ToolStatus.SUCCESS)
        assert success_count >= 1, f"{tenant} starvation detected in soak run"

    # Inject explicit invalid submissions for t3 to produce stable anomaly signal.
    for idx in range(6):
        bad = runtimes["t3"].submit_result(
            tenant_id="t3",
            worker_token=tokens["t3"],
            request_nonce=f"soak-bad-submit-{idx}",
            result=ByocToolResultEnvelope(
                job_id=f"missing-job-{idx}",
                tenant_id="t3",
                run_id=f"run-missing-{idx}",
                call_id=f"call-missing-{idx}",
                tool_name="echo_tool",
                status=ByocResultStatus.ERROR,
                output={},
                idempotency_key=f"soak-bad-idem-{idx}",
                lease_token="missing-lease",
            ),
        )
        assert bad.accepted is False

    # Runtime-control metrics include fairness indicators for each tenant.
    for tenant in tenants:
        stats_resp = client.get(f"/tenants/{tenant}/admin/runtime/control-stats", headers=_headers(tenant))
        assert stats_resp.status_code == 200
        stats = stats_resp.json()["control_stats"]
        assert "fair_admission_timeout_total" in stats
        assert "tenant_fair_admission_timeout_total" in stats
        assert stats["fair_admission_enabled"] == 1

    # Governance anomaly report should flag rejection-rate spike on stress tenant.
    metrics_resp = client.get("/tenants/t3/admin/byoc/governance-metrics", headers=_headers("t3"))
    assert metrics_resp.status_code == 200
    anomaly_codes = {item["code"] for item in metrics_resp.json()["anomaly_report"]["anomalies"]}
    assert "BYOC_REJECTION_RATE_SPIKE" in anomaly_codes
