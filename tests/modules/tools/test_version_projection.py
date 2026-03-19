"""
File: test_version_projection.py
Path: tests/modules/tools/test_version_projection.py
Role: Unit tests for projecting tool-version records into executable descriptors.
Used By:
 - pytest
Depends On:
 - src/tools/version_projection.py
 - src/persistence/contracts.py
Notes:
 - Covers handler resolution, inline/artifact validation, and integrity checks.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from src.persistence.contracts import (
    ToolPackageManifest,
    ToolValidationResult,
    ToolValidationState,
    ToolVersionRecord,
)
from src.tools.artifact_store import (
    ARTIFACT_BUNDLE_HASH_METADATA_KEY,
    ARTIFACT_BUNDLE_SIGNATURE_METADATA_KEY,
    ARTIFACT_HANDLER_PATH_METADATA_KEY,
    ARTIFACT_MANIFEST_PATH_METADATA_KEY,
    ARTIFACT_SIGNATURE_VERSION_METADATA_KEY,
    DEFAULT_ARTIFACT_SIGNATURE_VERSION,
    sign_bundle_hash,
)
from src.tools.version_projection import (
    INLINE_HANDLER_SOURCE_METADATA_KEY,
    _resolve_artifact_handler,
    _resolve_inline_handler,
    descriptor_from_tool_version,
    resolve_version_handler_ref,
    validate_inline_handler_source,
    verify_artifact_bundle_integrity,
)


def _record(
    *,
    metadata: dict | None = None,
    validation_state: ToolValidationState = ToolValidationState.VALID,
    risk_tier: str = "low",
    timeout_ms: int = 30000,
) -> ToolVersionRecord:
    return ToolVersionRecord(
        tenant_id="t1",
        tool_name="compute",
        version="1.0.0",
        manifest=ToolPackageManifest(
            tool_name="compute",
            version="1.0.0",
            description="compute helper",
            input_schema={"type": "object"},
            timeout_ms=timeout_ms,
            risk_tier=risk_tier,
            metadata=metadata or {},
        ),
        validation=ToolValidationResult(
            tool_name="compute",
            version="1.0.0",
            state=validation_state,
            normalized_schema_hash="h1",
        ),
        package_ref="pkg:1.0.0",
        active=True,
        created_at="2026-01-01T00:00:00Z",
    )


def test_validate_inline_handler_source_rejects_syntax_error() -> None:
    with pytest.raises(ValueError, match="invalid syntax"):
        validate_inline_handler_source("def run(:\n  pass", "run")


def test_validate_inline_handler_source_requires_entrypoint() -> None:
    with pytest.raises(ValueError, match="does not define entrypoint function 'run'"):
        validate_inline_handler_source("def other():\n    return 1\n", "run")


def test_descriptor_from_tool_version_rejects_invalid_validation_state() -> None:
    record = _record(validation_state=ToolValidationState.INVALID)
    with pytest.raises(ValueError, match="is invalid and cannot be activated"):
        descriptor_from_tool_version(record)


def test_descriptor_from_tool_version_resolves_handler_ref_module_function() -> None:
    record = _record(metadata={"handler_ref": "math:sqrt", "is_state_changing": False}, risk_tier="critical")
    descriptor = descriptor_from_tool_version(record)
    assert descriptor.name == "compute"
    assert descriptor.handler is math.sqrt
    assert descriptor.risk_tier.value == "critical"
    assert descriptor.is_state_changing is False
    assert descriptor.timeout_ms == 30000
    assert descriptor.metadata["handler_ref"] == "math:sqrt"


def test_descriptor_from_tool_version_defaults_risk_to_low_and_timeout_floor() -> None:
    record = _record(metadata={"handler_ref": "math:sqrt"}, risk_tier="not-a-tier", timeout_ms=0)
    descriptor = descriptor_from_tool_version(record)
    assert descriptor.risk_tier.value == "low"
    assert descriptor.timeout_ms == 1


def test_descriptor_from_tool_version_rejects_bad_handler_ref_formats() -> None:
    bad_ref_record = _record(metadata={"handler_ref": "not_valid_ref"})
    with pytest.raises(ValueError, match="Invalid handler_ref format"):
        descriptor_from_tool_version(bad_ref_record)

    missing_module_record = _record(metadata={"handler_ref": "missing_module_xyz:run"})
    with pytest.raises(ValueError, match="Module 'missing_module_xyz' not found"):
        descriptor_from_tool_version(missing_module_record)

    missing_function_record = _record(metadata={"handler_ref": "math:not_there"})
    with pytest.raises(ValueError, match="Function 'not_there' not found"):
        descriptor_from_tool_version(missing_function_record)


def test_descriptor_from_tool_version_rejects_non_callable_handler_ref() -> None:
    record = _record(metadata={"handler_ref": "math:pi"})
    with pytest.raises(ValueError, match="is not callable"):
        descriptor_from_tool_version(record)


def test_resolve_version_handler_ref_falls_back_to_default_when_missing() -> None:
    record = _record(metadata={})
    assert resolve_version_handler_ref(record) == "src.tools.user_tools:compute"


def test_descriptor_from_tool_version_uses_inline_source_handler() -> None:
    source = "def run(x=1):\n    return x + 2\n"
    record = _record(metadata={INLINE_HANDLER_SOURCE_METADATA_KEY: source})
    descriptor = descriptor_from_tool_version(record)
    assert descriptor.metadata["inline_handler"] is True
    assert descriptor.metadata["handler_ref"] == "inline://uploaded-source"
    assert descriptor.handler(x=3) == 5


def test_descriptor_from_tool_version_inline_source_runtime_validation_errors() -> None:
    record_empty = _record(metadata={INLINE_HANDLER_SOURCE_METADATA_KEY: ""})
    with pytest.raises(ValueError, match="inline handler source is empty"):
        _resolve_inline_handler(record_empty)

    record_not_callable = _record(metadata={INLINE_HANDLER_SOURCE_METADATA_KEY: "run = 3\n"})
    with pytest.raises(ValueError, match="does not define entrypoint"):
        _resolve_inline_handler(record_not_callable)


def test_resolve_inline_handler_runtime_entrypoint_guards(monkeypatch: pytest.MonkeyPatch) -> None:
    # Bypass AST precheck to exercise runtime guards.
    monkeypatch.setattr("src.tools.version_projection.validate_inline_handler_source", lambda source, entrypoint: None)

    missing_runtime = _record(metadata={INLINE_HANDLER_SOURCE_METADATA_KEY: "value = 1\n"})
    with pytest.raises(ValueError, match="does not expose entrypoint 'run' at runtime"):
        _resolve_inline_handler(missing_runtime)

    non_callable_runtime = _record(metadata={INLINE_HANDLER_SOURCE_METADATA_KEY: "run = 42\n"})
    with pytest.raises(ValueError, match="is not callable"):
        _resolve_inline_handler(non_callable_runtime)


def test_verify_artifact_bundle_integrity_requires_required_metadata(tmp_path: Path) -> None:
    record = _record(metadata={})
    with pytest.raises(ValueError, match="requires persisted manifest and handler paths"):
        verify_artifact_bundle_integrity(record, "secret")

    manifest_path = tmp_path / "tool.yaml"
    handler_path = tmp_path / "handler.py"
    manifest_path.write_text("tool_name: compute\n", encoding="utf-8")
    handler_path.write_text("def run():\n    return 1\n", encoding="utf-8")

    missing_hash = _record(
        metadata={
            ARTIFACT_MANIFEST_PATH_METADATA_KEY: str(manifest_path),
            ARTIFACT_HANDLER_PATH_METADATA_KEY: str(handler_path),
            ARTIFACT_BUNDLE_SIGNATURE_METADATA_KEY: "abc",
        }
    )
    with pytest.raises(ValueError, match="missing bundle hash"):
        verify_artifact_bundle_integrity(missing_hash, "secret")

    missing_signature = _record(
        metadata={
            ARTIFACT_MANIFEST_PATH_METADATA_KEY: str(manifest_path),
            ARTIFACT_HANDLER_PATH_METADATA_KEY: str(handler_path),
            ARTIFACT_BUNDLE_HASH_METADATA_KEY: "abc",
        }
    )
    with pytest.raises(ValueError, match="missing bundle signature"):
        verify_artifact_bundle_integrity(missing_signature, "secret")


def test_verify_artifact_bundle_integrity_detects_hash_and_signature_failures(tmp_path: Path) -> None:
    manifest_path = tmp_path / "tool.yaml"
    handler_path = tmp_path / "handler.py"
    manifest_path.write_text("tool_name: compute\nversion: 1.0.0\n", encoding="utf-8")
    handler_path.write_text("def run(x=1):\n    return x + 1\n", encoding="utf-8")

    record_bad_hash = _record(
        metadata={
            ARTIFACT_MANIFEST_PATH_METADATA_KEY: str(manifest_path),
            ARTIFACT_HANDLER_PATH_METADATA_KEY: str(handler_path),
            ARTIFACT_BUNDLE_HASH_METADATA_KEY: "0" * 64,
            ARTIFACT_BUNDLE_SIGNATURE_METADATA_KEY: "deadbeef",
        }
    )
    with pytest.raises(ValueError, match="bundle hash mismatch"):
        verify_artifact_bundle_integrity(record_bad_hash, "secret")

    # Compute valid hash but wrong signature.
    from src.tools.artifact_store import compute_bundle_hash_from_files

    bundle_hash = compute_bundle_hash_from_files(str(manifest_path), str(handler_path))
    record_bad_sig = _record(
        metadata={
            ARTIFACT_MANIFEST_PATH_METADATA_KEY: str(manifest_path),
            ARTIFACT_HANDLER_PATH_METADATA_KEY: str(handler_path),
            ARTIFACT_BUNDLE_HASH_METADATA_KEY: bundle_hash,
            ARTIFACT_BUNDLE_SIGNATURE_METADATA_KEY: "bad_signature",
            ARTIFACT_SIGNATURE_VERSION_METADATA_KEY: DEFAULT_ARTIFACT_SIGNATURE_VERSION,
        }
    )
    with pytest.raises(ValueError, match="invalid bundle signature"):
        verify_artifact_bundle_integrity(record_bad_sig, "secret")


def test_descriptor_from_tool_version_uses_artifact_handler_and_integrity(tmp_path: Path) -> None:
    manifest_path = tmp_path / "tool.yaml"
    handler_path = tmp_path / "handler.py"
    manifest_path.write_text("tool_name: compute\nversion: 1.0.0\n", encoding="utf-8")
    handler_path.write_text("def run(x=1):\n    return x * 3\n", encoding="utf-8")

    from src.tools.artifact_store import compute_bundle_hash_from_files

    bundle_hash = compute_bundle_hash_from_files(str(manifest_path), str(handler_path))
    signature = sign_bundle_hash(bundle_hash, "secret", DEFAULT_ARTIFACT_SIGNATURE_VERSION)

    record = _record(
        metadata={
            ARTIFACT_MANIFEST_PATH_METADATA_KEY: str(manifest_path),
            ARTIFACT_HANDLER_PATH_METADATA_KEY: str(handler_path),
            ARTIFACT_BUNDLE_HASH_METADATA_KEY: bundle_hash,
            ARTIFACT_BUNDLE_SIGNATURE_METADATA_KEY: signature,
            ARTIFACT_SIGNATURE_VERSION_METADATA_KEY: DEFAULT_ARTIFACT_SIGNATURE_VERSION,
        }
    )
    descriptor = descriptor_from_tool_version(record, artifact_signing_secret="secret")
    assert descriptor.metadata["artifact_handler"] is True
    assert descriptor.metadata["handler_ref"] == "artifact://uploaded-bundle"
    assert descriptor.handler(x=2) == 6


def test_descriptor_from_tool_version_artifact_resolution_errors(tmp_path: Path) -> None:
    manifest_path = tmp_path / "tool.yaml"
    handler_path = tmp_path / "handler.py"
    manifest_path.write_text("tool_name: compute\nversion: 1.0.0\n", encoding="utf-8")
    handler_path.write_text("x = 1\n", encoding="utf-8")

    from src.tools.artifact_store import compute_bundle_hash_from_files

    bundle_hash = compute_bundle_hash_from_files(str(manifest_path), str(handler_path))
    signature = sign_bundle_hash(bundle_hash, "secret", DEFAULT_ARTIFACT_SIGNATURE_VERSION)

    record_missing_entrypoint = _record(
        metadata={
            ARTIFACT_MANIFEST_PATH_METADATA_KEY: str(manifest_path),
            ARTIFACT_HANDLER_PATH_METADATA_KEY: str(handler_path),
            ARTIFACT_BUNDLE_HASH_METADATA_KEY: bundle_hash,
            ARTIFACT_BUNDLE_SIGNATURE_METADATA_KEY: signature,
            ARTIFACT_SIGNATURE_VERSION_METADATA_KEY: DEFAULT_ARTIFACT_SIGNATURE_VERSION,
        }
    )
    with pytest.raises(ValueError, match="does not define entrypoint 'run'"):
        descriptor_from_tool_version(record_missing_entrypoint, artifact_signing_secret="secret")


def test_resolve_artifact_handler_empty_and_missing_file_errors() -> None:
    empty_path_record = _record(metadata={ARTIFACT_HANDLER_PATH_METADATA_KEY: ""})
    with pytest.raises(ValueError, match="artifact handler path is empty"):
        _resolve_artifact_handler(empty_path_record)

    missing_path_record = _record(metadata={ARTIFACT_HANDLER_PATH_METADATA_KEY: "/tmp/definitely_missing_12345.py"})
    with pytest.raises(ValueError, match="does not exist"):
        _resolve_artifact_handler(missing_path_record)


def test_resolve_artifact_handler_loader_and_callable_guards(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    handler_path = tmp_path / "handler.py"
    handler_path.write_text("run = 7\n", encoding="utf-8")
    record = _record(metadata={ARTIFACT_HANDLER_PATH_METADATA_KEY: str(handler_path)})
    with pytest.raises(ValueError, match="is not callable"):
        _resolve_artifact_handler(record)

    class _Spec:
        loader = None

    monkeypatch.setattr("src.tools.version_projection.importlib.util.spec_from_file_location", lambda *a, **k: _Spec())
    with pytest.raises(ValueError, match="failed to load artifact handler module"):
        _resolve_artifact_handler(record)
