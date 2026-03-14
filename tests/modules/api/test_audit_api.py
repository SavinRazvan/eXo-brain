"""
File: test_audit_api.py
Path: tests/modules/api/test_audit_api.py
Role: API tests for tenant-scoped audit query and reporting endpoints.
Used By:
 - pytest
Depends On:
 - src/api/routers/audit.py
 - src/api/routers/tools.py
Notes:
 - Exercises lifecycle governance actions to generate audit records.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi.testclient import TestClient

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
from src.config.settings import AppSettings, LimitsSettings, RuntimeSettings
from src.compliance.evidence_bundle import sign_bundle_payload
from src.runtime.openai_agents_runtime import OpenAIAgentsRuntimeAdapter


def _x_identity(tenant_id: str = "t1", roles: list[str] | None = None) -> dict:
    return {
        "X-Identity": json.dumps(
            {
                "subject": "audit@test.com",
                "roles": roles or ["admin"],
                "tenant_id": tenant_id,
                "token_validation_state": "valid",
            }
        )
    }


def _build_sqlite_test_app(db_path: Path, settings_override: AppSettings | None = None):
    import os

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


def test_audit_events_and_report_endpoints(tmp_path: Path) -> None:
    app = _build_sqlite_test_app(tmp_path / "exo_audit_api.db")
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
                },
                "activate": True,
            },
            headers=_x_identity(),
        )
        assert upload.status_code == 201, upload.text

        deactivate = client.post(
            "/tenants/t1/tools/versions/calculate_result/1.0.0/deactivate",
            headers=_x_identity(),
        )
        assert deactivate.status_code == 200, deactivate.text

        corr = "t1:calculate_result:1.0.0"
        by_correlation = client.get(
            f"/tenants/t1/admin/audit/events?correlation_id={corr}",
            headers=_x_identity(),
        )
        assert by_correlation.status_code == 200, by_correlation.text
        payload = by_correlation.json()
        assert payload["tenant_id"] == "t1"
        assert payload["total"] >= 1
        assert any(event["event_type"] in {"tool_upload_saved", "tool_version_deactivated"} for event in payload["events"])

        report = client.get("/tenants/t1/admin/audit/report", headers=_x_identity())
        assert report.status_code == 200, report.text
        summary = report.json()
        assert summary["tenant_id"] == "t1"
        assert summary["total_events"] >= 1
        assert "tool_upload_saved" in summary["by_event_type"]

        export = client.get("/tenants/t1/admin/audit/export?limit=50", headers=_x_identity())
        assert export.status_code == 200, export.text
        bundle = export.json()
        assert bundle["tenant_id"] == "t1"
        assert bundle["record_count"] >= 1
        assert bundle["chain_valid"] is True
        assert "tool_upload_saved" in bundle["event_type_counts"]

        # Keep only one most-recent record and verify cleanup reports pruning.
        cleanup = client.post(
            "/tenants/t1/admin/audit/cleanup",
            json={"max_records": 1},
            headers=_x_identity(),
        )
        assert cleanup.status_code == 200, cleanup.text
        cleanup_body = cleanup.json()
        assert cleanup_body["tenant_id"] == "t1"
        assert cleanup_body["retained_cap"] == 1
        assert cleanup_body["pruned_records"] >= 1

        listed = client.get("/tenants/t1/admin/audit/events?limit=10", headers=_x_identity())
        assert listed.status_code == 200
        assert listed.json()["total"] <= 1


def test_audit_export_file_and_verify_endpoint(tmp_path: Path) -> None:
    export_dir = tmp_path / "audit_exports"
    settings = AppSettings(
        schema_version="1.0",
        environment="test",
        runtime=RuntimeSettings(
            default_provider_id="openai-test",
            allowed_provider_ids=["openai-test"],
            require_provider_healthcheck_on_start=False,
        ),
        limits=LimitsSettings(
            audit_export_directory=str(export_dir),
            audit_bundle_signing_secret="slice-6-3-test-secret",
            max_audit_export_records=100,
        ),
    )
    app = _build_sqlite_test_app(tmp_path / "exo_audit_verify.db", settings_override=settings)
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
                },
                "activate": True,
            },
            headers=_x_identity(),
        )
        assert upload.status_code == 201, upload.text

        export_resp = client.post(
            "/tenants/t1/admin/audit/export-file",
            json={"limit": 50, "filename_prefix": "tenant_audit"},
            headers=_x_identity(roles=["admin", "entitlement_enterprise"]),
        )
        assert export_resp.status_code == 200, export_resp.text
        exported = export_resp.json()
        assert exported["tenant_id"] == "t1"
        assert exported["record_count"] >= 1
        file_path = Path(exported["file_path"])
        assert file_path.exists()
        assert str(file_path).startswith(str(export_dir.resolve()))

        verify_ok = client.post(
            "/tenants/t1/admin/audit/verify",
            json={"file_path": str(file_path)},
            headers=_x_identity(roles=["admin", "entitlement_enterprise"]),
        )
        assert verify_ok.status_code == 200, verify_ok.text
        verified = verify_ok.json()
        assert verified["verified"] is True
        assert verified["signature_valid"] is True
        assert verified["chain_valid"] is True
        assert verified["verified_with_version"] == "v1"

        # Tamper bundle payload and verify failure.
        tampered = json.loads(file_path.read_text(encoding="utf-8"))
        tampered["record_count"] = int(tampered.get("record_count", 0)) + 1
        verify_fail = client.post(
            "/tenants/t1/admin/audit/verify",
            json={"bundle": tampered},
            headers=_x_identity(roles=["admin", "entitlement_enterprise"]),
        )
        assert verify_fail.status_code == 200, verify_fail.text
        failed = verify_fail.json()
        assert failed["verified"] is False
        assert failed["signature_valid"] is False or failed["chain_valid"] is False


def test_audit_signed_export_requires_enterprise_entitlement(tmp_path: Path) -> None:
    export_dir = tmp_path / "audit_exports_entitlement"
    settings = AppSettings(
        schema_version="1.0",
        environment="test",
        runtime=RuntimeSettings(
            default_provider_id="openai-test",
            allowed_provider_ids=["openai-test"],
            require_provider_healthcheck_on_start=False,
        ),
        limits=LimitsSettings(
            audit_export_directory=str(export_dir),
            audit_bundle_signing_secret="slice-6-3-test-secret",
            max_audit_export_records=100,
        ),
    )
    app = _build_sqlite_test_app(tmp_path / "exo_audit_entitlement.db", settings_override=settings)
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
                },
                "activate": True,
            },
            headers=_x_identity(),
        )
        assert upload.status_code == 201, upload.text

        denied = client.post(
            "/tenants/t1/admin/audit/export-file",
            json={"limit": 50, "filename_prefix": "tenant_audit"},
            headers=_x_identity(roles=["admin", "entitlement_pro"]),
        )
        assert denied.status_code == 403
        assert "ENTITLEMENT_TIER_REQUIRED" in denied.text

        records = asyncio.run(app.state.audit_store.list_audit_events(tenant_id="t1", limit=20))
        entitlement = [record for record in records if record.event_type == "entitlement_decision"]
        assert entitlement
        latest = entitlement[-1]
        assert latest.payload.get("surface") == "audit_signed_export_verify"
        assert latest.payload.get("feature") == "governance.audit.signed_export_verify"
        assert latest.payload.get("decision") == "deny"
        assert latest.payload.get("required_tier") == "enterprise"
        assert latest.payload.get("current_tier") == "pro"


def test_audit_verify_supports_key_rotation_and_legacy_signature_version(tmp_path: Path) -> None:
    export_dir = tmp_path / "audit_exports_rotated"
    settings = AppSettings(
        schema_version="1.0",
        environment="test",
        runtime=RuntimeSettings(
            default_provider_id="openai-test",
            allowed_provider_ids=["openai-test"],
            require_provider_healthcheck_on_start=False,
        ),
        limits=LimitsSettings(
            audit_export_directory=str(export_dir),
            audit_bundle_signing_secret="legacy-v1-secret",
            audit_bundle_signing_active_version="v2",
            audit_bundle_signing_secrets_by_version={
                "v1": "legacy-v1-secret",
                "v2": "rotated-v2-secret",
            },
            max_audit_export_records=100,
        ),
    )
    app = _build_sqlite_test_app(tmp_path / "exo_audit_rotation.db", settings_override=settings)
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
                },
                "activate": True,
            },
            headers=_x_identity(),
        )
        assert upload.status_code == 201, upload.text

        exported = client.get("/tenants/t1/admin/audit/export?limit=50", headers=_x_identity())
        assert exported.status_code == 200, exported.text
        bundle = exported.json()
        assert bundle["signature_version"] == "v2"

        verify_current = client.post(
            "/tenants/t1/admin/audit/verify",
            json={"bundle": bundle},
            headers=_x_identity(roles=["admin", "entitlement_enterprise"]),
        )
        assert verify_current.status_code == 200, verify_current.text
        verify_current_payload = verify_current.json()
        assert verify_current_payload["verified"] is True
        assert verify_current_payload["signature_valid"] is True
        assert verify_current_payload["verified_with_version"] == "v2"

        legacy_payload = dict(bundle)
        legacy_payload.pop("signature", None)
        legacy_payload.pop("signature_version", None)
        legacy_signature = sign_bundle_payload(legacy_payload, "legacy-v1-secret")
        legacy_bundle = dict(legacy_payload)
        legacy_bundle["signature"] = legacy_signature
        verify_legacy = client.post(
            "/tenants/t1/admin/audit/verify",
            json={"bundle": legacy_bundle},
            headers=_x_identity(roles=["admin", "entitlement_enterprise"]),
        )
        assert verify_legacy.status_code == 200, verify_legacy.text
        verify_legacy_payload = verify_legacy.json()
        assert verify_legacy_payload["verified"] is True
        assert verify_legacy_payload["signature_valid"] is True
        assert verify_legacy_payload["verified_with_version"] == "v1"
