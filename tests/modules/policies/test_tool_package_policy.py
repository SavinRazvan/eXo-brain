"""
File: test_tool_package_policy.py
Path: tests/modules/policies/test_tool_package_policy.py
Role: Unit tests for tool package upload validation policy.
Used By:
 - pytest
Depends On:
 - src/policies/tool_package_policy.py
 - src/persistence/contracts.py
 - src/config/settings.py
Notes:
 - Covers size gates, ref tokens, requirement tokens, and allowlist behavior.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from src.config.settings import LimitsSettings
from src.persistence.contracts import ToolPackageManifest
from src.policies.tool_package_policy import validate_tool_package_upload


def _manifest(**kwargs: object) -> ToolPackageManifest:
    base = ToolPackageManifest(
        tool_name="t",
        version="1",
        description="d",
        entry_file="handler.py",
        entrypoint="run",
        risk_tier="low",
        timeout_ms=1000,
        requirements=["requests"],
    )
    return replace(base, **kwargs)


def _limits(**kwargs: object) -> LimitsSettings:
    base = LimitsSettings()
    return replace(base, **kwargs)


def test_validate_warns_when_artifact_size_zero() -> None:
    decision = validate_tool_package_upload(
        manifest=_manifest(),
        package_ref="pkg",
        artifact_size_bytes=0,
        limits=_limits(),
    )
    assert decision.allowed is True
    assert any("artifact_size_bytes was not provided" in w for w in decision.warnings)


def test_validate_rejects_oversized_artifact() -> None:
    decision = validate_tool_package_upload(
        manifest=_manifest(),
        package_ref="pkg",
        artifact_size_bytes=999_999_999,
        limits=_limits(max_tool_upload_size_bytes=100),
    )
    assert decision.allowed is False
    assert any("exceeds max_tool_upload_size_bytes" in e for e in decision.errors)


def test_validate_rejects_long_package_ref() -> None:
    decision = validate_tool_package_upload(
        manifest=_manifest(),
        package_ref="x" * 2049,
        artifact_size_bytes=1,
        limits=_limits(),
    )
    assert decision.allowed is False
    assert any("2048" in e for e in decision.errors)


def test_validate_rejects_blocked_package_ref_token() -> None:
    decision = validate_tool_package_upload(
        manifest=_manifest(),
        package_ref="evil..path",
        artifact_size_bytes=1,
        limits=_limits(),
    )
    assert decision.allowed is False
    assert any("blocked token" in e for e in decision.errors)


def test_validate_rejects_requirement_with_blocked_token() -> None:
    decision = validate_tool_package_upload(
        manifest=_manifest(requirements=["git+https://x/y"]),
        package_ref="pkg",
        artifact_size_bytes=1,
        limits=_limits(),
    )
    assert decision.allowed is False
    assert any("blocked token" in e for e in decision.errors)


def test_validate_rejects_malformed_requirement_name() -> None:
    decision = validate_tool_package_upload(
        manifest=_manifest(requirements=["!!!not-a-name"]),
        package_ref="pkg",
        artifact_size_bytes=1,
        limits=_limits(),
    )
    assert decision.allowed is False
    assert any("invalid package name format" in e for e in decision.errors)


def test_validate_rejects_requirement_not_on_allowlist() -> None:
    decision = validate_tool_package_upload(
        manifest=_manifest(requirements=["requests>=1"]),
        package_ref="pkg",
        artifact_size_bytes=1,
        limits=_limits(allowed_tool_dependency_prefixes=["internal_"]),
    )
    assert decision.allowed is False
    assert any("allowlist" in e for e in decision.errors)
