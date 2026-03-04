"""
File: test_deployment_profile_defaults.py
Path: tests/modules/api/test_deployment_profile_defaults.py
Role: Verify deployment profile default settings mapping in app factory.
Used By:
 - pytest
Depends On:
 - src/api/app.py
Notes:
 - Focuses on default fallbacks when explicit env overrides are absent.
"""

from __future__ import annotations

from src.api.app import create_app


def test_self_hosted_profile_applies_default_storage_paths(monkeypatch) -> None:
    monkeypatch.setenv("EXO_DEPLOYMENT_PROFILE", "self_hosted")
    monkeypatch.delenv("EXO_TOOL_ARTIFACT_DIRECTORY", raising=False)
    monkeypatch.delenv("EXO_AUDIT_EXPORT_DIRECTORY", raising=False)
    monkeypatch.delenv("EXO_BYOC_STORE_BACKEND", raising=False)
    app = create_app()
    settings = app.state.settings
    assert settings.deployment_profile.value == "self_hosted"
    assert settings.limits.tool_artifact_directory.endswith("/self_hosted")
    assert settings.limits.audit_export_directory.endswith("/self_hosted")
    assert settings.runtime.byoc_store_backend == "sqlite"


def test_hybrid_profile_applies_distinct_defaults(monkeypatch) -> None:
    monkeypatch.setenv("EXO_DEPLOYMENT_PROFILE", "hybrid")
    monkeypatch.delenv("EXO_TOOL_ARTIFACT_DIRECTORY", raising=False)
    monkeypatch.delenv("EXO_AUDIT_EXPORT_DIRECTORY", raising=False)
    app = create_app()
    settings = app.state.settings
    assert settings.deployment_profile.value == "hybrid"
    assert settings.limits.tool_artifact_directory.endswith("/hybrid")
    assert settings.limits.audit_export_directory.endswith("/hybrid")

