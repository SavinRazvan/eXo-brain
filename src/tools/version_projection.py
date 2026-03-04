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

import importlib
from typing import Any, Callable

from src.persistence.contracts import ToolValidationState, ToolVersionRecord
from src.schemas.tool_io import RiskTier
from src.tools.registry import ToolDescriptor
from src.tools.user_tool_contracts import default_handler_ref


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


def descriptor_from_tool_version(record: ToolVersionRecord) -> ToolDescriptor:
    validation = record.validation
    if validation is not None and validation.state == ToolValidationState.INVALID:
        raise ValueError(f"Tool version '{record.tool_name}@{record.version}' is invalid and cannot be activated.")
    handler_ref = resolve_version_handler_ref(record)
    handler = _resolve_handler(handler_ref)
    metadata = dict(record.manifest.metadata or {})
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
