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
from src.schemas.tool_io import ToolCallContext, ToolStatus


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


def test_upload_returns_429_when_tenant_upload_rate_limit_exceeded(tmp_path: Path) -> None:
    from src.config.settings import AppSettings, LimitsSettings, RuntimeSettings

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
