"""
File: user_tool_contracts.py
Path: src/tools/user_tool_contracts.py
Role: Normalize tenant tool payloads into canonical tool package contracts.
Used By:
 - src/api/routers/tools.py
 - ui/src/screens/tools.ts
Depends On:
 - dataclasses
 - hashlib
 - json
Notes:
 - Accepts OpenAI-style function payloads and raw JSON Schema payloads.
 - This module is contract-only and does not execute user code.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any


DEFAULT_USER_TOOLS_MODULE = "src.tools.user_tools"
SANDBOX_LIMITS_METADATA_KEY = "sandbox_limits"
SANDBOX_CPU_BUDGET_MS_KEY = "cpu_budget_ms"
SANDBOX_MEMORY_BUDGET_MB_KEY = "memory_budget_mb"
SANDBOX_CPU_BUDGET_MS_MIN = 10
SANDBOX_CPU_BUDGET_MS_MAX = 600000
SANDBOX_MEMORY_BUDGET_MB_MIN = 16
SANDBOX_MEMORY_BUDGET_MB_MAX = 4096


@dataclass(slots=True)
class NormalizedToolPayload:
    """Canonical normalized tool fields extracted from user payloads."""

    name: str
    description: str
    parameters_schema: dict[str, Any]


@dataclass(slots=True)
class SandboxLimits:
    """Normalized runtime budgets parsed from manifest metadata."""

    cpu_budget_ms: int | None = None
    memory_budget_mb: int | None = None


def default_handler_ref(tool_name: str) -> str:
    """Return canonical handler path for user-defined tools."""
    return f"{DEFAULT_USER_TOOLS_MODULE}:{tool_name}"


def normalize_tool_payload(payload: dict[str, Any]) -> NormalizedToolPayload:
    """Normalize tool payloads from OpenAI-style or raw schema inputs.

    Supported forms:
    - {"name": "...", "description": "...", "parameters": {...}}
    - {"type": "function", "function": {"name": "...", "description": "...", "parameters": {...}}}
    - {"type": "object", ...}  # raw JSON schema (name required externally)
    """
    if not isinstance(payload, dict):
        raise ValueError("Tool payload must be a JSON object.")

    candidate: dict[str, Any] = payload
    if payload.get("type") == "function":
        fn = payload.get("function")
        if not isinstance(fn, dict):
            raise ValueError("Function wrapper payload must include object field 'function'.")
        candidate = fn

    name = str(candidate.get("name", "")).strip()
    description = str(candidate.get("description", "")).strip()

    if isinstance(candidate.get("parameters"), dict):
        schema = candidate["parameters"]
    else:
        schema = candidate

    if not isinstance(schema, dict):
        raise ValueError("Tool parameters schema must be a JSON object.")

    return NormalizedToolPayload(
        name=name,
        description=description,
        parameters_schema=schema,
    )


def schema_fingerprint(parameters_schema: dict[str, Any]) -> str:
    """Return stable SHA-256 fingerprint for a normalized schema object."""
    stable_json = json.dumps(parameters_schema, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(stable_json.encode("utf-8")).hexdigest()


def parse_sandbox_limits(metadata: dict[str, Any]) -> SandboxLimits | None:
    """Parse and validate sandbox runtime limits from manifest metadata.

    Expected shape:
    metadata = {
      "sandbox_limits": {
        "cpu_budget_ms": 5000,
        "memory_budget_mb": 256
      }
    }
    """
    if not isinstance(metadata, dict):
        raise ValueError("metadata must be an object")

    raw_limits = metadata.get(SANDBOX_LIMITS_METADATA_KEY)
    if raw_limits is None:
        return None
    if not isinstance(raw_limits, dict):
        raise ValueError(f"metadata.{SANDBOX_LIMITS_METADATA_KEY} must be an object")

    cpu = _parse_optional_int(
        raw_limits,
        SANDBOX_CPU_BUDGET_MS_KEY,
        minimum=SANDBOX_CPU_BUDGET_MS_MIN,
        maximum=SANDBOX_CPU_BUDGET_MS_MAX,
    )
    memory = _parse_optional_int(
        raw_limits,
        SANDBOX_MEMORY_BUDGET_MB_KEY,
        minimum=SANDBOX_MEMORY_BUDGET_MB_MIN,
        maximum=SANDBOX_MEMORY_BUDGET_MB_MAX,
    )
    return SandboxLimits(cpu_budget_ms=cpu, memory_budget_mb=memory)


def normalize_manifest_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """Return metadata normalized to canonical sandbox limit keys."""
    limits = parse_sandbox_limits(metadata)
    normalized = dict(metadata)
    if limits is None:
        return normalized
    normalized[SANDBOX_LIMITS_METADATA_KEY] = {
        SANDBOX_CPU_BUDGET_MS_KEY: limits.cpu_budget_ms,
        SANDBOX_MEMORY_BUDGET_MB_KEY: limits.memory_budget_mb,
    }
    return normalized


def _parse_optional_int(
    payload: dict[str, Any],
    key: str,
    *,
    minimum: int,
    maximum: int,
) -> int | None:
    value = payload.get(key)
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} must be an integer") from exc
    if parsed < minimum or parsed > maximum:
        raise ValueError(f"{key} must be between {minimum} and {maximum}")
    return parsed
