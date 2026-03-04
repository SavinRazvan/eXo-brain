"""
File: version_projection.py
Path: src/tools/version_projection.py
Role: Project active ToolVersionStore records into executable ToolDescriptor instances.
Used By:
 - src/api/routers/tools.py
 - src/api/startup.py
Depends On:
 - src/persistence/contracts.py
 - src/tools/registry.py
 - src/tools/user_tool_contracts.py
Notes:
 - Activation remains deterministic: invalid or unresolvable versions cannot be projected.
"""

from __future__ import annotations

import ast
import importlib
import importlib.util
import hmac
import re
from pathlib import Path
from typing import Any, Callable

from src.persistence.contracts import ToolValidationState, ToolVersionRecord
from src.schemas.tool_io import RiskTier
from src.tools.artifact_store import (
    ARTIFACT_BUNDLE_HASH_METADATA_KEY,
    ARTIFACT_BUNDLE_SIGNATURE_METADATA_KEY,
    ARTIFACT_HANDLER_PATH_METADATA_KEY,
    ARTIFACT_MANIFEST_PATH_METADATA_KEY,
    ARTIFACT_SIGNATURE_VERSION_METADATA_KEY,
    DEFAULT_ARTIFACT_SIGNATURE_VERSION,
    compute_bundle_hash_from_files,
    verify_bundle_signature,
)
from src.tools.registry import ToolDescriptor
from src.tools.user_tool_contracts import default_handler_ref

INLINE_HANDLER_SOURCE_METADATA_KEY = "inline_handler_source"


def _inline_source_from_metadata(record: ToolVersionRecord) -> str:
    metadata = dict(record.manifest.metadata or {})
    return str(metadata.get(INLINE_HANDLER_SOURCE_METADATA_KEY, "")).strip()


def _artifact_handler_path_from_metadata(record: ToolVersionRecord) -> str:
    metadata = dict(record.manifest.metadata or {})
    return str(metadata.get(ARTIFACT_HANDLER_PATH_METADATA_KEY, "")).strip()


def _artifact_manifest_path_from_metadata(record: ToolVersionRecord) -> str:
    metadata = dict(record.manifest.metadata or {})
    return str(metadata.get(ARTIFACT_MANIFEST_PATH_METADATA_KEY, "")).strip()


def validate_inline_handler_source(source: str, entrypoint: str) -> None:
    """Validate inline source without executing user code.

    This gate checks syntax and verifies the configured entrypoint function name
    exists in the parsed module AST.
    """
    try:
        module_ast = ast.parse(source, mode="exec")
    except SyntaxError as exc:
        raise ValueError(f"inline handler source has invalid syntax: {exc.msg}") from exc
    has_entrypoint = any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == entrypoint
        for node in module_ast.body
    )
    if not has_entrypoint:
        raise ValueError(f"inline handler source does not define entrypoint function '{entrypoint}'")


def _resolve_inline_handler(record: ToolVersionRecord) -> Callable[..., Any]:
    source = _inline_source_from_metadata(record)
    if not source:
        raise ValueError("inline handler source is empty")
    entrypoint = str(record.manifest.entrypoint or "run").strip() or "run"
    validate_inline_handler_source(source, entrypoint)
    module_name = f"tenant_tool_{record.tenant_id}_{record.tool_name}_{record.version}".replace("-", "_")
    module_globals: dict[str, Any] = {"__name__": module_name}
    exec(compile(source, f"<{module_name}>", "exec"), module_globals, module_globals)
    resolved = module_globals.get(entrypoint)
    if resolved is None:
        raise ValueError(f"inline handler source does not expose entrypoint '{entrypoint}' at runtime")
    if not callable(resolved):
        raise ValueError(f"inline entrypoint '{entrypoint}' is not callable")
    return resolved


def _resolve_artifact_handler(record: ToolVersionRecord) -> Callable[..., Any]:
    handler_path = _artifact_handler_path_from_metadata(record)
    if not handler_path:
        raise ValueError("artifact handler path is empty")
    path = Path(handler_path)
    if not path.exists() or not path.is_file():
        raise ValueError(f"artifact handler file does not exist: {handler_path}")
    entrypoint = str(record.manifest.entrypoint or "run").strip() or "run"
    safe_module_suffix = re.sub(r"[^A-Za-z0-9_]+", "_", f"{record.tenant_id}_{record.tool_name}_{record.version}")
    module_name = f"tenant_tool_artifact_{safe_module_suffix}"
    spec = importlib.util.spec_from_file_location(module_name, str(path))
    if spec is None or spec.loader is None:
        raise ValueError(f"failed to load artifact handler module from {handler_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    resolved = getattr(module, entrypoint, None)
    if resolved is None:
        raise ValueError(f"artifact handler does not define entrypoint '{entrypoint}'")
    if not callable(resolved):
        raise ValueError(f"artifact entrypoint '{entrypoint}' is not callable")
    return resolved


def verify_artifact_bundle_integrity(record: ToolVersionRecord, signing_secret: str) -> None:
    metadata = dict(record.manifest.metadata or {})
    manifest_path = _artifact_manifest_path_from_metadata(record)
    handler_path = _artifact_handler_path_from_metadata(record)
    expected_hash = str(metadata.get(ARTIFACT_BUNDLE_HASH_METADATA_KEY, "")).strip()
    expected_signature = str(metadata.get(ARTIFACT_BUNDLE_SIGNATURE_METADATA_KEY, "")).strip()
    signature_version = str(metadata.get(ARTIFACT_SIGNATURE_VERSION_METADATA_KEY, "")).strip()
    if not manifest_path or not handler_path:
        raise ValueError("artifact integrity verification requires persisted manifest and handler paths")
    if not expected_hash:
        raise ValueError("artifact integrity metadata is missing bundle hash")
    if not expected_signature:
        raise ValueError("artifact integrity metadata is missing bundle signature")
    if not signature_version:
        signature_version = DEFAULT_ARTIFACT_SIGNATURE_VERSION
    actual_hash = compute_bundle_hash_from_files(manifest_path, handler_path)
    if not hmac.compare_digest(actual_hash, expected_hash):
        raise ValueError("artifact integrity verification failed: bundle hash mismatch")
    if not verify_bundle_signature(
        bundle_hash=actual_hash,
        signature=expected_signature,
        signing_secret=signing_secret,
        version=signature_version,
    ):
        raise ValueError("artifact integrity verification failed: invalid bundle signature")


def resolve_version_handler_ref(record: ToolVersionRecord) -> str:
    metadata = dict(record.manifest.metadata or {})
    handler_ref = str(metadata.get("handler_ref", "")).strip()
    if handler_ref:
        return handler_ref
    return default_handler_ref(record.tool_name)


def _resolve_handler(handler_ref: str) -> Callable[..., Any]:
    if ":" not in handler_ref:
        raise ValueError(f"Invalid handler_ref format '{handler_ref}'. Expected 'module.path:function_name'.")
    module_path, func_name = handler_ref.rsplit(":", 1)
    try:
        module = importlib.import_module(module_path)
    except ModuleNotFoundError as exc:
        raise ValueError(f"Module '{module_path}' not found: {exc}") from exc
    func = getattr(module, func_name, None)
    if func is None:
        raise ValueError(f"Function '{func_name}' not found in module '{module_path}'")
    if not callable(func):
        raise ValueError(f"'{func_name}' in '{module_path}' is not callable")
    return func


def descriptor_from_tool_version(record: ToolVersionRecord, artifact_signing_secret: str = "") -> ToolDescriptor:
    validation = record.validation
    if validation is not None and validation.state == ToolValidationState.INVALID:
        raise ValueError(f"Tool version '{record.tool_name}@{record.version}' is invalid and cannot be activated.")
    metadata = dict(record.manifest.metadata or {})
    artifact_handler_path = _artifact_handler_path_from_metadata(record)
    inline_source = _inline_source_from_metadata(record)
    if artifact_handler_path:
        verify_artifact_bundle_integrity(record, artifact_signing_secret)
        handler = _resolve_artifact_handler(record)
        handler_ref = "artifact://uploaded-bundle"
        metadata["artifact_handler"] = True
    elif inline_source:
        handler = _resolve_inline_handler(record)
        handler_ref = "inline://uploaded-source"
        metadata["inline_handler"] = True
    else:
        handler_ref = resolve_version_handler_ref(record)
        handler = _resolve_handler(handler_ref)
    metadata.update(
        {
            "handler_ref": handler_ref,
            "tool_version": record.version,
            "package_ref": record.package_ref,
            "entry_file": record.manifest.entry_file,
            "entrypoint": record.manifest.entrypoint,
            "source": "tool_version_store",
        }
    )
    risk_tier_raw = str(record.manifest.risk_tier or "low").lower()
    try:
        risk_tier = RiskTier(risk_tier_raw)
    except ValueError:
        risk_tier = RiskTier.LOW
    return ToolDescriptor(
        name=record.tool_name,
        handler=handler,
        risk_tier=risk_tier,
        is_state_changing=bool(metadata.get("is_state_changing", True)),
        timeout_ms=max(int(record.manifest.timeout_ms), 1),
        description=record.manifest.description or "",
        parameters_schema=dict(record.manifest.input_schema or {}),
        metadata=metadata,
    )
