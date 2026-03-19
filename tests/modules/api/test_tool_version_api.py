"""
File: test_tool_version_api.py
Path: tests/modules/api/test_tool_version_api.py
Role: Acceptance tests for tenant tool import/upload/validate/version endpoints.
Used By:
 - pytest
Depends On:
 - src/api/routers/tools.py
 - src/api/bootstrap.py
Notes:
 - Uses both memory backend (503 checks) and SQLite backend (happy path).
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi.testclient import TestClient

from src.api.bootstrap import build_test_app
from src.api.routers import tools as tools_router
from src.schemas.tool_io import ToolCallContext, ToolStatus
from src.tenancy import rate_limiter as rate_limiter_module


def _x_identity(tenant_id: str = "t1") -> dict:
    return {
        "X-Identity": json.dumps(
            {
                "subject": "user@test.com",
                "roles": ["admin"],
                "tenant_id": tenant_id,
                "token_validation_state": "valid",
            }
        )
    }


def _build_sqlite_test_app(db_path: Path, settings_override=None):
    import os
    from src.api.app import create_app
    from src.api.bootstrap import bootstrap
    from src.config.provider_registry import (
        AuthConfig,
        EndpointApiType,
        EndpointConfig,
        ModelDefaults,
        ProviderProfile,
        ProviderRecord,
        ProviderRegistry,
    )
    from src.config.settings import AppSettings, RuntimeSettings
    from src.runtime.openai_agents_runtime import OpenAIAgentsRuntimeAdapter

    settings = settings_override or AppSettings(
        schema_version="1.0",
        environment="test",
        runtime=RuntimeSettings(
            default_provider_id="openai-test",
            allowed_provider_ids=["openai-test"],
            require_provider_healthcheck_on_start=False,
        ),
    )
    adapter = OpenAIAgentsRuntimeAdapter(provider_id="openai-test")
    record = ProviderRecord(
        provider_id="openai-test",
        display_name="Test OpenAI",
        adapter_class="OpenAIAgentsRuntimeAdapter",
        enabled=True,
        profile=ProviderProfile.MANAGED_VENDOR,
        priority=1,
        endpoint=EndpointConfig(base_url="https://api.openai.com", api_type=EndpointApiType.OPENAI_NATIVE),
        auth=AuthConfig(type="api_key", api_key_env_var=""),
        model_defaults=ModelDefaults(model="gpt-4o-mini"),
    )
    provider_registry = ProviderRegistry(settings=settings, providers=[record], adapters={"openai-test": adapter})
    app = create_app()
    old = os.environ.get("EXO_DB_PATH")
    os.environ["EXO_DB_PATH"] = str(db_path)
    try:
        bootstrap(app, provider_registry, settings, persistence_backend="sqlite")
    finally:
        if old is None:
            os.environ.pop("EXO_DB_PATH", None)
        else:
            os.environ["EXO_DB_PATH"] = old
    return app


def test_import_schema_normalizes_openai_function_payload() -> None:
    app = build_test_app()
    with TestClient(app) as client:
        resp = client.post(
            "/tenants/t1/tools/import-schema",
            json={
                "payload": {
                    "type": "function",
                    "function": {
                        "name": "calculate_result",
                        "description": "math helper",
                        "parameters": {"type": "object", "properties": {"x": {"type": "number"}}},
                    },
                }
            },
            headers=_x_identity(),
        )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["tool_name"] == "calculate_result"
    assert data["handler_ref"] == "src.tools.user_tools:calculate_result"
    assert data["parameters_schema"]["type"] == "object"
    assert data["schema_fingerprint"]


def test_upload_returns_503_with_memory_backend() -> None:
    app = build_test_app()
    with TestClient(app) as client:
        resp = client.post(
            "/tenants/t1/tools/upload",
            json={
                "manifest": {
                    "tool_name": "calculate_result",
                    "version": "1.0.0",
                    "input_schema": {"type": "object"},
                    "risk_tier": "low",
                }
            },
            headers=_x_identity(),
        )
    assert resp.status_code == 503


def test_upload_validate_and_list_versions_with_sqlite(tmp_path: Path) -> None:
    app = _build_sqlite_test_app(tmp_path / "exo.db")
    with TestClient(app) as client:
        up = client.post(
            "/tenants/t1/tools/upload",
            json={
                "manifest": {
                    "tool_name": "calculate_result",
                    "version": "1.0.0",
                    "description": "math",
                    "input_schema": {"type": "object", "properties": {"x": {"type": "number"}}},
                    "risk_tier": "low",
                    "entry_file": "handler.py",
                    "entrypoint": "run",
                },
                "package_ref": "pkg://calc/1.0.0",
                "activate": True,
            },
            headers=_x_identity(),
        )
        assert up.status_code == 201, up.text
        assert up.json()["active"] is True
        assert up.json()["state"] == "valid"

        validate = client.get("/tenants/t1/tools/validate/calculate_result", headers=_x_identity())
        assert validate.status_code == 200
        assert validate.json()["version"] == "1.0.0"
        assert validate.json()["state"] == "valid"

        versions = client.get("/tenants/t1/tools/versions/calculate_result", headers=_x_identity())
        assert versions.status_code == 200
        assert versions.json()["total"] == 1

        alias = client.get("/tenants/t1/tools/version/calculate_result", headers=_x_identity())
        assert alias.status_code == 200
        assert alias.json()["total"] == 1


def test_upload_marks_manifest_invalid_for_bad_sandbox_limits(tmp_path: Path) -> None:
    app = _build_sqlite_test_app(tmp_path / "exo_bad_limits.db")
    with TestClient(app) as client:
        up = client.post(
            "/tenants/t1/tools/upload",
            json={
                "manifest": {
                    "tool_name": "calculate_result",
                    "version": "2.0.0",
                    "input_schema": {"type": "object"},
                    "risk_tier": "low",
                    "entry_file": "handler.py",
                    "entrypoint": "run",
                    "metadata": {
                        "sandbox_limits": {
                            "memory_budget_mb": "not-an-int",
                        }
                    },
                },
                "activate": True,
            },
            headers=_x_identity(),
        )
        assert up.status_code == 201, up.text
        assert up.json()["state"] == "invalid"
        assert any("memory_budget_mb must be an integer" in err for err in up.json()["errors"])


def test_upload_accepts_valid_sandbox_limits_metadata(tmp_path: Path) -> None:
    app = _build_sqlite_test_app(tmp_path / "exo_good_limits.db")
    with TestClient(app) as client:
        up = client.post(
            "/tenants/t1/tools/upload",
            json={
                "manifest": {
                    "tool_name": "calculate_result",
                    "version": "3.0.0",
                    "input_schema": {"type": "object"},
                    "risk_tier": "low",
                    "entry_file": "handler.py",
                    "entrypoint": "run",
                    "metadata": {
                        "sandbox_limits": {
                            "cpu_budget_ms": 5000,
                            "memory_budget_mb": 256,
                        }
                    },
                },
                "activate": True,
            },
            headers=_x_identity(),
        )
        assert up.status_code == 201, up.text
        assert up.json()["state"] == "valid"


def test_upload_rejects_when_artifact_size_exceeds_limit(tmp_path: Path) -> None:
    app = _build_sqlite_test_app(tmp_path / "exo_artifact_limit.db")
    with TestClient(app) as client:
        up = client.post(
            "/tenants/t1/tools/upload",
            json={
                "manifest": {
                    "tool_name": "calculate_result",
                    "version": "4.0.0",
                    "input_schema": {"type": "object"},
                    "risk_tier": "low",
                    "entry_file": "handler.py",
                    "entrypoint": "run",
                },
                "artifact_size_bytes": 5_000_001,
                "activate": True,
            },
            headers=_x_identity(),
        )
    assert up.status_code == 201, up.text
    assert up.json()["state"] == "invalid"
    assert any("artifact_size_bytes exceeds max_tool_upload_size_bytes" in err for err in up.json()["errors"])


def test_upload_rejects_dependency_outside_allowlist(tmp_path: Path) -> None:
    from src.config.settings import AppSettings, LimitsSettings, RuntimeSettings

    settings = AppSettings(
        schema_version="1.0",
        environment="test",
        runtime=RuntimeSettings(
            default_provider_id="openai-test",
            allowed_provider_ids=["openai-test"],
            require_provider_healthcheck_on_start=False,
        ),
        limits=LimitsSettings(
            allowed_tool_dependency_prefixes=["numpy", "pydantic"],
        ),
    )
    app = _build_sqlite_test_app(tmp_path / "exo_requirements_allowlist.db", settings_override=settings)
    with TestClient(app) as client:
        up = client.post(
            "/tenants/t1/tools/upload",
            json={
                "manifest": {
                    "tool_name": "calculate_result",
                    "version": "5.0.0",
                    "input_schema": {"type": "object"},
                    "risk_tier": "low",
                    "entry_file": "handler.py",
                    "entrypoint": "run",
                    "requirements": ["requests>=2.0.0"],
                },
                "activate": True,
            },
            headers=_x_identity(),
        )
    assert up.status_code == 201, up.text
    assert up.json()["state"] == "invalid"
    assert any("not allowed by dependency allowlist" in err for err in up.json()["errors"])


def test_upload_returns_429_when_tenant_upload_rate_limit_exceeded(tmp_path: Path, monkeypatch) -> None:
    from src.config.settings import AppSettings, LimitsSettings, RuntimeSettings

    # Pin fixed-window clock to prevent minute-boundary flakes during long suites.
    monkeypatch.setattr(rate_limiter_module.time, "time", lambda: 1_700_000_000)

    settings = AppSettings(
        schema_version="1.0",
        environment="test",
        runtime=RuntimeSettings(
            default_provider_id="openai-test",
            allowed_provider_ids=["openai-test"],
            require_provider_healthcheck_on_start=False,
        ),
        limits=LimitsSettings(max_tool_uploads_per_minute_per_tenant=1),
    )
    app = _build_sqlite_test_app(tmp_path / "exo_upload_rate_limit.db", settings_override=settings)
    with TestClient(app) as client:
        first = client.post(
            "/tenants/t1/tools/upload",
            json={
                "manifest": {
                    "tool_name": "calculate_result",
                    "version": "6.0.0",
                    "input_schema": {"type": "object"},
                    "risk_tier": "low",
                    "entry_file": "handler.py",
                    "entrypoint": "run",
                },
            },
            headers=_x_identity(),
        )
        assert first.status_code == 201, first.text
        second = client.post(
            "/tenants/t1/tools/upload",
            json={
                "manifest": {
                    "tool_name": "calculate_result",
                    "version": "6.0.1",
                    "input_schema": {"type": "object"},
                    "risk_tier": "low",
                    "entry_file": "handler.py",
                    "entrypoint": "run",
                },
            },
            headers=_x_identity(),
        )
    assert second.status_code == 429
    assert "TENANT_UPLOAD_RATE_LIMIT_EXCEEDED" in second.text


def test_deactivate_rollback_and_revoke_tool_versions(tmp_path: Path) -> None:
    app = _build_sqlite_test_app(tmp_path / "exo_lifecycle_ops.db")
    with TestClient(app) as client:
        v1 = client.post(
            "/tenants/t1/tools/upload",
            json={
                "manifest": {
                    "tool_name": "calculate_result",
                    "version": "1.0.0",
                    "input_schema": {"type": "object"},
                    "risk_tier": "low",
                    "entry_file": "handler.py",
                    "entrypoint": "run",
                },
                "activate": True,
            },
            headers=_x_identity(),
        )
        assert v1.status_code == 201, v1.text
        v2 = client.post(
            "/tenants/t1/tools/upload",
            json={
                "manifest": {
                    "tool_name": "calculate_result",
                    "version": "2.0.0",
                    "input_schema": {"type": "object"},
                    "risk_tier": "low",
                    "entry_file": "handler.py",
                    "entrypoint": "run",
                },
                "activate": True,
            },
            headers=_x_identity(),
        )
        assert v2.status_code == 201, v2.text
        assert v2.json()["active"] is True

        deact = client.post(
            "/tenants/t1/tools/versions/calculate_result/2.0.0/deactivate",
            headers=_x_identity(),
        )
        assert deact.status_code == 200, deact.text
        assert deact.json()["action"] == "deactivate"
        versions_after_deact = client.get("/tenants/t1/tools/versions/calculate_result", headers=_x_identity())
        assert versions_after_deact.status_code == 200
        assert all(not bool(row["active"]) for row in versions_after_deact.json()["versions"])

        rollback = client.post(
            "/tenants/t1/tools/versions/calculate_result/rollback",
            json={"target_version": "1.0.0"},
            headers=_x_identity(),
        )
        assert rollback.status_code == 200, rollback.text
        assert rollback.json()["active_version"] == "1.0.0"
        versions_after_rollback = client.get("/tenants/t1/tools/versions/calculate_result", headers=_x_identity())
        assert versions_after_rollback.status_code == 200
        rows = versions_after_rollback.json()["versions"]
        active_rows = [row for row in rows if row["active"]]
        assert len(active_rows) == 1
        assert active_rows[0]["version"] == "1.0.0"

        revoke_conflict = client.delete(
            "/tenants/t1/tools/versions/calculate_result/1.0.0",
            headers=_x_identity(),
        )
        assert revoke_conflict.status_code == 409

        revoke_force = client.delete(
            "/tenants/t1/tools/versions/calculate_result/1.0.0?force=true",
            headers=_x_identity(),
        )
        assert revoke_force.status_code == 200, revoke_force.text
        assert revoke_force.json()["revoked"] is True
        versions_after_revoke = client.get("/tenants/t1/tools/versions/calculate_result", headers=_x_identity())
        assert versions_after_revoke.status_code == 200
        remaining_versions = [row["version"] for row in versions_after_revoke.json()["versions"]]
        assert "1.0.0" not in remaining_versions


def test_active_uploaded_version_drives_runtime_execution_and_rollback(tmp_path: Path) -> None:
    app = _build_sqlite_test_app(tmp_path / "exo_runtime_version_wiring.db")
    with TestClient(app) as client:
        v1 = client.post(
            "/tenants/t1/tools/upload",
            json={
                "manifest": {
                    "tool_name": "calculate_result",
                    "version": "1.0.0",
                    "input_schema": {"type": "object"},
                    "risk_tier": "low",
                    "entry_file": "handler.py",
                    "entrypoint": "run",
                    "metadata": {"handler_ref": "src.tools.user_tools:calculate_result"},
                },
                "package_ref": "pkg://calc/1.0.0",
                "activate": True,
            },
            headers=_x_identity(),
        )
        assert v1.status_code == 201, v1.text
        assert v1.json()["active"] is True

        ctx = app.state.tenant_factory.get_or_create("t1")
        call_v1 = ToolCallContext(
            schema_version="1.0",
            call_id="call_version_v1",
            session_id="sess_v1",
            run_id="run_v1",
            job_id="job_v1",
            task_id="task_v1",
            agent_id="agent_v1",
            provider_id="openai-test",
            tenant_id="t1",
            tool_name="calculate_result",
            arguments={"operation": "add", "operand1": 2, "operand2": 3},
        )
        result_v1 = ctx.tool_executor.execute(call_v1)
        assert result_v1.status == ToolStatus.SUCCESS
        assert result_v1.result is not None
        assert result_v1.result.get("runtime", {}).get("tool_version") == "1.0.0"

        v2 = client.post(
            "/tenants/t1/tools/upload",
            json={
                "manifest": {
                    "tool_name": "calculate_result",
                    "version": "2.0.0",
                    "input_schema": {"type": "object"},
                    "risk_tier": "low",
                    "entry_file": "handler.py",
                    "entrypoint": "run",
                    "metadata": {"handler_ref": "src.tools.user_tools:calculate_result"},
                },
                "package_ref": "pkg://calc/2.0.0",
                "activate": True,
            },
            headers=_x_identity(),
        )
        assert v2.status_code == 201, v2.text
        assert v2.json()["active"] is True

        call_v2 = ToolCallContext(
            schema_version="1.0",
            call_id="call_version_v2",
            session_id="sess_v2",
            run_id="run_v2",
            job_id="job_v2",
            task_id="task_v2",
            agent_id="agent_v2",
            provider_id="openai-test",
            tenant_id="t1",
            tool_name="calculate_result",
            arguments={"operation": "add", "operand1": 4, "operand2": 6},
        )
        result_v2 = ctx.tool_executor.execute(call_v2)
        assert result_v2.status == ToolStatus.SUCCESS
        assert result_v2.result is not None
        assert result_v2.result.get("runtime", {}).get("tool_version") == "2.0.0"

        rollback = client.post(
            "/tenants/t1/tools/versions/calculate_result/rollback",
            json={"target_version": "1.0.0"},
            headers=_x_identity(),
        )
        assert rollback.status_code == 200, rollback.text
        assert rollback.json()["active_version"] == "1.0.0"

        call_after_rollback = ToolCallContext(
            schema_version="1.0",
            call_id="call_version_after_rollback",
            session_id="sess_v3",
            run_id="run_v3",
            job_id="job_v3",
            task_id="task_v3",
            agent_id="agent_v3",
            provider_id="openai-test",
            tenant_id="t1",
            tool_name="calculate_result",
            arguments={"operation": "add", "operand1": 1, "operand2": 1},
        )
        result_after_rollback = ctx.tool_executor.execute(call_after_rollback)
        assert result_after_rollback.status == ToolStatus.SUCCESS
        assert result_after_rollback.result is not None
        assert result_after_rollback.result.get("runtime", {}).get("tool_version") == "1.0.0"


def test_startup_hydrates_active_tool_versions_into_registry(tmp_path: Path) -> None:
    db_path = tmp_path / "exo_runtime_hydration.db"
    app = _build_sqlite_test_app(db_path)
    with TestClient(app) as client:
        upload = client.post(
            "/tenants/t1/tools/upload",
            json={
                "manifest": {
                    "tool_name": "calculate_result",
                    "version": "1.0.0",
                    "input_schema": {"type": "object"},
                    "risk_tier": "low",
                    "entry_file": "handler.py",
                    "entrypoint": "run",
                    "metadata": {"handler_ref": "src.tools.user_tools:calculate_result"},
                },
                "package_ref": "pkg://calc/1.0.0",
                "activate": True,
            },
            headers=_x_identity(),
        )
        assert upload.status_code == 201, upload.text

    restarted = _build_sqlite_test_app(db_path)
    with TestClient(restarted):
        ctx = restarted.state.tenant_factory.get_or_create("t1")
        descriptor = ctx.tool_registry.resolve("calculate_result")
        assert descriptor.metadata.get("tool_version") == "1.0.0"
        assert descriptor.metadata.get("source") == "tool_version_store"


def test_inline_uploaded_source_executes_and_rollback_switches_behavior(tmp_path: Path) -> None:
    app = _build_sqlite_test_app(tmp_path / "exo_inline_uploads.db")
    v1_source = """
def run(operation: str, operand1: float, operand2: float) -> dict:
    if operation != "add":
        raise ValueError("unsupported operation")
    return {"result": operand1 + operand2, "impl": "v1"}
""".strip()
    v2_source = """
def run(operation: str, operand1: float, operand2: float) -> dict:
    if operation != "add":
        raise ValueError("unsupported operation")
    return {"result": (operand1 + operand2) * 10, "impl": "v2"}
""".strip()
    with TestClient(app) as client:
        upload_v1 = client.post(
            "/tenants/t1/tools/upload",
            json={
                "manifest": {
                    "tool_name": "inline_calc",
                    "version": "1.0.0",
                    "input_schema": {"type": "object"},
                    "risk_tier": "low",
                    "entry_file": "handler.py",
                    "entrypoint": "run",
                },
                "inline_handler_source": v1_source,
                "activate": True,
            },
            headers=_x_identity(),
        )
        assert upload_v1.status_code == 201, upload_v1.text
        assert upload_v1.json()["active"] is True
        assert upload_v1.json()["state"] == "valid"

        ctx = app.state.tenant_factory.get_or_create("t1")
        descriptor_v1 = ctx.tool_registry.resolve("inline_calc")
        artifact_handler_v1 = descriptor_v1.metadata.get("artifact_handler_path", "")
        artifact_manifest_v1 = descriptor_v1.metadata.get("artifact_manifest_path", "")
        assert artifact_handler_v1
        assert artifact_manifest_v1
        assert Path(str(artifact_handler_v1)).exists()
        assert Path(str(artifact_manifest_v1)).exists()
        stored_v1 = asyncio.run(app.state.tool_version_store.get_tool_version("t1", "inline_calc", "1.0.0"))
        assert stored_v1 is not None
        assert stored_v1.manifest.metadata.get("artifact_handler_path")
        assert stored_v1.manifest.metadata.get("artifact_manifest_path")
        first_call = ToolCallContext(
            schema_version="1.0",
            call_id="inline_call_v1",
            session_id="inline_sess_v1",
            run_id="inline_run_v1",
            job_id="inline_job_v1",
            task_id="inline_task_v1",
            agent_id="inline_agent_v1",
            provider_id="openai-test",
            tenant_id="t1",
            tool_name="inline_calc",
            arguments={"operation": "add", "operand1": 2, "operand2": 3},
        )
        first_result = ctx.tool_executor.execute(first_call)
        assert first_result.status == ToolStatus.SUCCESS
        assert first_result.result is not None
        assert first_result.result["value"]["result"] == 5
        assert first_result.result["value"]["impl"] == "v1"
        assert first_result.result.get("runtime", {}).get("tool_version") == "1.0.0"

        upload_v2 = client.post(
            "/tenants/t1/tools/upload",
            json={
                "manifest": {
                    "tool_name": "inline_calc",
                    "version": "2.0.0",
                    "input_schema": {"type": "object"},
                    "risk_tier": "low",
                    "entry_file": "handler.py",
                    "entrypoint": "run",
                },
                "inline_handler_source": v2_source,
                "activate": True,
            },
            headers=_x_identity(),
        )
        assert upload_v2.status_code == 201, upload_v2.text
        assert upload_v2.json()["active"] is True
        assert upload_v2.json()["state"] == "valid"

        second_call = ToolCallContext(
            schema_version="1.0",
            call_id="inline_call_v2",
            session_id="inline_sess_v2",
            run_id="inline_run_v2",
            job_id="inline_job_v2",
            task_id="inline_task_v2",
            agent_id="inline_agent_v2",
            provider_id="openai-test",
            tenant_id="t1",
            tool_name="inline_calc",
            arguments={"operation": "add", "operand1": 2, "operand2": 3},
        )
        second_result = ctx.tool_executor.execute(second_call)
        assert second_result.status == ToolStatus.SUCCESS
        assert second_result.result is not None
        assert second_result.result["value"]["result"] == 50
        assert second_result.result["value"]["impl"] == "v2"
        assert second_result.result.get("runtime", {}).get("tool_version") == "2.0.0"
        descriptor_v2 = ctx.tool_registry.resolve("inline_calc")
        assert descriptor_v2.metadata.get("handler_ref") == "artifact://uploaded-bundle"

        rollback = client.post(
            "/tenants/t1/tools/versions/inline_calc/rollback",
            json={"target_version": "1.0.0"},
            headers=_x_identity(),
        )
        assert rollback.status_code == 200, rollback.text
        assert rollback.json()["active_version"] == "1.0.0"

        after_rollback_call = ToolCallContext(
            schema_version="1.0",
            call_id="inline_call_after_rollback",
            session_id="inline_sess_v3",
            run_id="inline_run_v3",
            job_id="inline_job_v3",
            task_id="inline_task_v3",
            agent_id="inline_agent_v3",
            provider_id="openai-test",
            tenant_id="t1",
            tool_name="inline_calc",
            arguments={"operation": "add", "operand1": 2, "operand2": 3},
        )
        after_rollback_result = ctx.tool_executor.execute(after_rollback_call)
        assert after_rollback_result.status == ToolStatus.SUCCESS
        assert after_rollback_result.result is not None
        assert after_rollback_result.result["value"]["result"] == 5
        assert after_rollback_result.result["value"]["impl"] == "v1"
        assert after_rollback_result.result.get("runtime", {}).get("tool_version") == "1.0.0"


def test_upload_with_explicit_package_bundle_persists_files_and_executes(tmp_path: Path) -> None:
    app = _build_sqlite_test_app(tmp_path / "exo_package_bundle_uploads.db")
    with TestClient(app) as client:
        upload = client.post(
            "/tenants/t1/tools/upload",
            json={
                "manifest": {
                    "tool_name": "bundle_calc",
                    "version": "1.0.0",
                    "description": "bundle-backed tool",
                    "input_schema": {"type": "object"},
                    "risk_tier": "low",
                    "entry_file": "handler.py",
                    "entrypoint": "run",
                },
                "package_bundle": {
                    "tool_yaml": "tool_name: bundle_calc\nversion: 1.0.0\n",
                    "handler_py": (
                        "def run(operation: str, operand1: float, operand2: float) -> dict:\n"
                        "    if operation != 'add':\n"
                        "        raise ValueError('unsupported operation')\n"
                        "    return {'result': operand1 + operand2, 'impl': 'bundle'}\n"
                    ),
                },
                "activate": True,
            },
            headers=_x_identity(),
        )
        assert upload.status_code == 201, upload.text
        assert upload.json()["state"] == "valid"
        assert upload.json()["active"] is True

        ctx = app.state.tenant_factory.get_or_create("t1")
        descriptor = ctx.tool_registry.resolve("bundle_calc")
        assert descriptor.metadata.get("handler_ref") == "artifact://uploaded-bundle"
        artifact_handler = Path(str(descriptor.metadata.get("artifact_handler_path", "")))
        artifact_manifest = Path(str(descriptor.metadata.get("artifact_manifest_path", "")))
        assert artifact_handler.exists()
        assert artifact_manifest.exists()

        call = ToolCallContext(
            schema_version="1.0",
            call_id="bundle_call_v1",
            session_id="bundle_sess_v1",
            run_id="bundle_run_v1",
            job_id="bundle_job_v1",
            task_id="bundle_task_v1",
            agent_id="bundle_agent_v1",
            provider_id="openai-test",
            tenant_id="t1",
            tool_name="bundle_calc",
            arguments={"operation": "add", "operand1": 7, "operand2": 8},
        )
        result = ctx.tool_executor.execute(call)
        assert result.status == ToolStatus.SUCCESS
        assert result.result is not None
        assert result.result["value"]["result"] == 15
        assert result.result["value"]["impl"] == "bundle"


def test_artifact_integrity_verification_blocks_tampered_version_activation(tmp_path: Path) -> None:
    app = _build_sqlite_test_app(tmp_path / "exo_bundle_integrity.db")
    with TestClient(app) as client:
        upload_v1 = client.post(
            "/tenants/t1/tools/upload",
            json={
                "manifest": {
                    "tool_name": "integrity_calc",
                    "version": "1.0.0",
                    "input_schema": {"type": "object"},
                    "risk_tier": "low",
                    "entry_file": "handler.py",
                    "entrypoint": "run",
                },
                "package_bundle": {
                    "tool_yaml": "tool_name: integrity_calc\nversion: 1.0.0\n",
                    "handler_py": (
                        "def run(operation: str, operand1: float, operand2: float) -> dict:\n"
                        "    if operation != 'add':\n"
                        "        raise ValueError('unsupported operation')\n"
                        "    return {'result': operand1 + operand2, 'impl': 'v1'}\n"
                    ),
                },
                "activate": True,
            },
            headers=_x_identity(),
        )
        assert upload_v1.status_code == 201, upload_v1.text
        assert upload_v1.json()["active"] is True

        upload_v2 = client.post(
            "/tenants/t1/tools/upload",
            json={
                "manifest": {
                    "tool_name": "integrity_calc",
                    "version": "2.0.0",
                    "input_schema": {"type": "object"},
                    "risk_tier": "low",
                    "entry_file": "handler.py",
                    "entrypoint": "run",
                },
                "package_bundle": {
                    "tool_yaml": "tool_name: integrity_calc\nversion: 2.0.0\n",
                    "handler_py": (
                        "def run(operation: str, operand1: float, operand2: float) -> dict:\n"
                        "    if operation != 'add':\n"
                        "        raise ValueError('unsupported operation')\n"
                        "    return {'result': (operand1 + operand2) * 10, 'impl': 'v2'}\n"
                    ),
                },
                "activate": True,
            },
            headers=_x_identity(),
        )
        assert upload_v2.status_code == 201, upload_v2.text
        assert upload_v2.json()["active"] is True

        stored_v1 = asyncio.run(app.state.tool_version_store.get_tool_version("t1", "integrity_calc", "1.0.0"))
        assert stored_v1 is not None
        handler_path = Path(str(stored_v1.manifest.metadata.get("artifact_handler_path", "")))
        assert handler_path.exists()
        handler_path.write_text(
            "def run(operation: str, operand1: float, operand2: float) -> dict:\n"
            "    return {'result': 999, 'impl': 'tampered'}\n",
            encoding="utf-8",
        )

        rollback = client.post(
            "/tenants/t1/tools/versions/integrity_calc/rollback",
            json={"target_version": "1.0.0"},
            headers=_x_identity(),
        )
        assert rollback.status_code == 422, rollback.text
        assert "bundle hash mismatch" in rollback.text


def test_resolve_handler_rejects_non_callable_attribute() -> None:
    try:
        tools_router._resolve_handler("os:path")
    except ValueError as exc:
        assert "is not callable" in str(exc)
    else:
        raise AssertionError("Expected non-callable handler_ref validation error.")


def test_tools_router_helper_validation_branches(monkeypatch) -> None:
    from src.persistence.contracts import (
        ToolPackageManifest,
        ToolValidationResult,
        ToolValidationState,
        ToolVersionRecord,
    )
    from src.tools.artifact_store import ARTIFACT_BUNDLE_HASH_METADATA_KEY, ARTIFACT_BUNDLE_SIGNATURE_METADATA_KEY

    manifest = ToolPackageManifest(
        tool_name="",
        version="",
        input_schema=[],
        entry_file="handler.txt",
        entrypoint="",
        metadata={"sandbox_limits": {"cpu_budget_ms": 10_000}},
    )
    result = tools_router._validation_for_manifest(manifest)
    assert result.state == ToolValidationState.INVALID
    assert "tool_name is required" in result.errors
    assert "version is required" in result.errors
    assert "entry_file must be a .py file" in result.errors
    assert "entrypoint is required" in result.errors
    assert "input_schema must be an object" in result.errors

    inline_manifest = ToolPackageManifest(
        tool_name="ok",
        version="1.0.0",
        input_schema={"type": "object"},
        entry_file="handler.py",
        entrypoint="run",
    )
    inline_bad = tools_router._validation_for_manifest(
        inline_manifest,
        inline_handler_source="def not_run():\n    return {}",
    )
    assert any("entrypoint" in err for err in inline_bad.errors)

    base = ToolVersionRecord(
        tenant_id="t1",
        tool_name="demo",
        version="1.0.0",
        package_ref="pkg://demo/1.0.0",
        manifest=ToolPackageManifest(
            tool_name="demo",
            version="1.0.0",
            input_schema={"type": "object"},
            entry_file="handler.py",
            entrypoint="run",
            metadata={"artifact_handler_path": "/tmp/h.py"},
        ),
        validation=ToolValidationResult(tool_name="demo", version="1.0.0", state=ToolValidationState.VALID),
        active=False,
    )
    missing = tools_router._to_validation_response(base, "secret")
    assert missing.integrity_status == "missing_metadata"

    base.manifest.metadata[ARTIFACT_BUNDLE_HASH_METADATA_KEY] = "hash"
    base.manifest.metadata[ARTIFACT_BUNDLE_SIGNATURE_METADATA_KEY] = "sig"
    unverifiable = tools_router._to_validation_response(base, "")
    assert unverifiable.integrity_status == "unverifiable"

    monkeypatch.setattr(
        tools_router,
        "verify_artifact_bundle_integrity",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("bundle mismatch")),
    )
    mismatch = tools_router._to_validation_response(base, "secret")
    assert mismatch.integrity_status == "mismatch"
    assert mismatch.integrity_message == "bundle mismatch"


def test_sync_active_descriptor_handles_missing_active_and_unregistered_tool() -> None:
    class _Registry:
        def unregister(self, _tool_name: str) -> None:
            raise KeyError("missing")

        def register(self, _descriptor) -> None:
            raise AssertionError("register should not be called")

    class _Ctx:
        tool_registry = _Registry()

    class _Store:
        async def get_active_tool_version(self, _tenant_id: str, _tool_name: str):
            return None

    asyncio.run(
        tools_router._sync_active_tool_descriptor(
            tenant_id="t1",
            tool_name="ghost",
            ctx=_Ctx(),
            tool_version_store=_Store(),
            artifact_signing_secret="secret",
        )
    )


def test_tools_router_memory_backend_error_branches() -> None:
    app = build_test_app()
    with TestClient(app) as client:
        validate = client.get("/tenants/t1/tools/validate/demo", headers=_x_identity())
        assert validate.status_code == 503
        versions = client.get("/tenants/t1/tools/versions/demo", headers=_x_identity())
        assert versions.status_code == 503
        deactivate = client.post("/tenants/t1/tools/versions/demo/1.0.0/deactivate", headers=_x_identity())
        assert deactivate.status_code == 503
        rollback = client.post(
            "/tenants/t1/tools/versions/demo/rollback",
            json={"target_version": "1.0.0"},
            headers=_x_identity(),
        )
        assert rollback.status_code == 503
        revoke = client.delete("/tenants/t1/tools/versions/demo/1.0.0", headers=_x_identity())
        assert revoke.status_code == 503


def test_import_schema_error_paths() -> None:
    app = build_test_app()
    with TestClient(app) as client:
        invalid_payload = client.post(
            "/tenants/t1/tools/import-schema",
            json={"payload": "not-a-valid-tool-schema"},
            headers=_x_identity(),
        )
        assert invalid_payload.status_code == 422
        missing_name = client.post(
            "/tenants/t1/tools/import-schema",
            json={"payload": {"description": "no name"}},
            headers=_x_identity(),
        )
        assert missing_name.status_code == 422
        assert "tool_name is required" in missing_name.text


def test_upload_inline_source_error_paths(tmp_path: Path, monkeypatch) -> None:
    app = _build_sqlite_test_app(tmp_path / "exo_tools_router_inline_errors.db")
    app.state.tool_artifact_store = None
    with TestClient(app) as client:
        no_store = client.post(
            "/tenants/t1/tools/upload",
            json={
                "manifest": {
                    "tool_name": "demo_inline",
                    "version": "1.0.0",
                    "input_schema": {"type": "object"},
                    "risk_tier": "low",
                    "entry_file": "handler.py",
                    "entrypoint": "run",
                },
                "inline_handler_source": "def run(**kwargs):\n    return kwargs",
            },
            headers=_x_identity(),
        )
        assert no_store.status_code == 503

    app2 = _build_sqlite_test_app(tmp_path / "exo_tools_router_signing_error.db")
    monkeypatch.setattr(
        tools_router,
        "sign_bundle_hash",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("signing unavailable")),
    )
    with TestClient(app2) as client:
        signing_fail = client.post(
            "/tenants/t1/tools/upload",
            json={
                "manifest": {
                    "tool_name": "demo_inline",
                    "version": "2.0.0",
                    "input_schema": {"type": "object"},
                    "risk_tier": "low",
                    "entry_file": "handler.py",
                    "entrypoint": "run",
                },
                "inline_handler_source": "def run(**kwargs):\n    return kwargs",
            },
            headers=_x_identity(),
        )
        assert signing_fail.status_code == 503


def test_upload_activate_descriptor_errors_and_active_record_fallback(tmp_path: Path, monkeypatch) -> None:
    app = _build_sqlite_test_app(tmp_path / "exo_tools_router_activate_errors.db")
    original_descriptor = tools_router.descriptor_from_tool_version
    with TestClient(app) as client:
        monkeypatch.setattr(
            tools_router,
            "descriptor_from_tool_version",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("descriptor invalid")),
        )
        upload = client.post(
            "/tenants/t1/tools/upload",
            json={
                "manifest": {
                    "tool_name": "demo",
                    "version": "1.0.0",
                    "input_schema": {"type": "object"},
                    "risk_tier": "low",
                    "entry_file": "handler.py",
                    "entrypoint": "run",
                },
                "activate": True,
            },
            headers=_x_identity(),
        )
        assert upload.status_code == 422
    monkeypatch.setattr(tools_router, "descriptor_from_tool_version", original_descriptor)

    app2 = _build_sqlite_test_app(tmp_path / "exo_tools_router_active_fallback.db")
    original_get_tool_version = app2.state.tool_version_store.get_tool_version

    async def _get_tool_version_none(*_args, **_kwargs):
        return None

    app2.state.tool_version_store.get_tool_version = _get_tool_version_none
    with TestClient(app2) as client:
        upload = client.post(
            "/tenants/t1/tools/upload",
            json={
                "manifest": {
                    "tool_name": "demo",
                    "version": "1.0.0",
                    "input_schema": {"type": "object"},
                    "risk_tier": "low",
                    "entry_file": "handler.py",
                    "entrypoint": "run",
                    "metadata": {"handler_ref": "src.tools.user_tools:calculate_result"},
                },
                "activate": True,
            },
            headers=_x_identity(),
        )
        assert upload.status_code == 201
        assert upload.json()["version"] == "1.0.0"
    app2.state.tool_version_store.get_tool_version = original_get_tool_version


def test_validate_without_version_uses_first_saved_version_when_no_active(tmp_path: Path) -> None:
    app = _build_sqlite_test_app(tmp_path / "exo_tools_router_validate_fallback.db")
    with TestClient(app) as client:
        upload = client.post(
            "/tenants/t1/tools/upload",
            json={
                "manifest": {
                    "tool_name": "demo",
                    "version": "1.0.0",
                    "input_schema": {"type": "object"},
                    "risk_tier": "low",
                    "entry_file": "handler.py",
                    "entrypoint": "run",
                },
                "activate": False,
            },
            headers=_x_identity(),
        )
        assert upload.status_code == 201
        validate = client.get("/tenants/t1/tools/validate/demo", headers=_x_identity())
        assert validate.status_code == 200
        assert validate.json()["version"] == "1.0.0"


def test_deactivate_rollback_and_revoke_negative_paths(tmp_path: Path) -> None:
    app = _build_sqlite_test_app(tmp_path / "exo_tools_router_negative_ops.db")
    with TestClient(app) as client:
        upload = client.post(
            "/tenants/t1/tools/upload",
            json={
                "manifest": {
                    "tool_name": "demo",
                    "version": "1.0.0",
                    "input_schema": {"type": "object"},
                    "risk_tier": "low",
                    "entry_file": "handler.py",
                    "entrypoint": "run",
                },
                "activate": False,
            },
            headers=_x_identity(),
        )
        assert upload.status_code == 201
        no_active = client.post("/tenants/t1/tools/versions/demo/1.0.0/deactivate", headers=_x_identity())
        assert no_active.status_code == 404

        active_v1 = client.post(
            "/tenants/t1/tools/upload",
            json={
                "manifest": {
                    "tool_name": "demo",
                    "version": "1.1.0",
                    "input_schema": {"type": "object"},
                    "risk_tier": "low",
                    "entry_file": "handler.py",
                    "entrypoint": "run",
                    "metadata": {"handler_ref": "src.tools.user_tools:calculate_result"},
                },
                "activate": True,
            },
            headers=_x_identity(),
        )
        assert active_v1.status_code == 201
        mismatch = client.post("/tenants/t1/tools/versions/demo/1.0.0/deactivate", headers=_x_identity())
        assert mismatch.status_code == 409

        missing_target = client.post(
            "/tenants/t1/tools/versions/demo/rollback",
            json={"target_version": "9.9.9"},
            headers=_x_identity(),
        )
        assert missing_target.status_code == 404

        invalid_upload = client.post(
            "/tenants/t1/tools/upload",
            json={
                "manifest": {
                    "tool_name": "demo",
                    "version": "2.0.0",
                    "input_schema": {"type": "object"},
                    "risk_tier": "low",
                    "entry_file": "handler.py",
                    "entrypoint": "run",
                    "metadata": {"sandbox_limits": {"memory_budget_mb": "bad"}},
                },
                "activate": False,
            },
            headers=_x_identity(),
        )
        assert invalid_upload.status_code == 201
        invalid_target = client.post(
            "/tenants/t1/tools/versions/demo/rollback",
            json={"target_version": "2.0.0"},
            headers=_x_identity(),
        )
        assert invalid_target.status_code == 409

        missing_version = client.delete("/tenants/t1/tools/versions/demo/0.0.0", headers=_x_identity())
        assert missing_version.status_code == 404


def test_register_unregister_and_import_internal_branches(monkeypatch) -> None:
    from src.api.schemas.tool_schemas import ToolImportSchemaRequest, ToolRegisterRequest
    from types import SimpleNamespace
    from src.tools.registry import ToolRegistry

    class _Store:
        def __init__(self) -> None:
            self.saved = 0
            self.deleted = 0

        async def save_tool(self, _tenant_id: str, _record) -> None:
            self.saved += 1

        async def delete_tool(self, _tenant_id: str, _name: str) -> None:
            self.deleted += 1

    ctx = SimpleNamespace(tool_registry=ToolRegistry())
    store = _Store()
    body = ToolRegisterRequest(name="calc", handler_ref="math:sqrt")
    identity = object()
    created = asyncio.run(
        tools_router.register_tool(
            tenant_id="t1",
            body=body,
            ctx=ctx,
            _identity=identity,
            tool_store=store,  # type: ignore[arg-type]
        )
    )
    assert created.name == "calc"
    assert store.saved == 1
    asyncio.run(
        tools_router.unregister_tool(
            tenant_id="t1",
            name="calc",
            ctx=ctx,
            _identity=identity,
            tool_store=store,  # type: ignore[arg-type]
        )
    )
    assert store.deleted == 1

    monkeypatch.setattr(
        tools_router,
        "normalize_tool_payload",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("bad payload")),
    )
    try:
        asyncio.run(
            tools_router.import_tool_schema(
                tenant_id="t1",
                body=ToolImportSchemaRequest(payload={"name": "x"}),
                _identity=identity,
            )
        )
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 422
    else:
        raise AssertionError("Expected import schema normalization failure.")


def test_manifest_warning_validate_version_and_missing_lookup_paths(tmp_path: Path) -> None:
    from src.persistence.contracts import ToolPackageManifest

    warning_validation = tools_router._validation_for_manifest(
        ToolPackageManifest(
            tool_name="demo",
            version="1.0.0",
            input_schema={"type": "object"},
            timeout_ms=100,
            entry_file="handler.py",
            entrypoint="custom",
            metadata={"sandbox_limits": {"cpu_budget_ms": 500}},
        )
    )
    assert any("cpu_budget_ms exceeds timeout_ms" in item for item in warning_validation.warnings)
    assert any("entrypoint is not the standard 'run'" in item for item in warning_validation.warnings)

    app = _build_sqlite_test_app(tmp_path / "exo_validate_version_path.db")
    with TestClient(app) as client:
        upload = client.post(
            "/tenants/t1/tools/upload",
            json={
                "manifest": {
                    "tool_name": "demo",
                    "version": "1.0.0",
                    "input_schema": {"type": "object"},
                    "risk_tier": "low",
                    "entry_file": "handler.py",
                    "entrypoint": "run",
                },
                "activate": False,
            },
            headers=_x_identity(),
        )
        assert upload.status_code == 201
        validate_specific = client.get("/tenants/t1/tools/validate/demo?version=1.0.0", headers=_x_identity())
        assert validate_specific.status_code == 200
        missing = client.get("/tenants/t1/tools/validate/ghost?version=1.0.0", headers=_x_identity())
        assert missing.status_code == 404
