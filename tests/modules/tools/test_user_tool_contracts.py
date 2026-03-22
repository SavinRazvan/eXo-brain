"""
File: test_user_tool_contracts.py
Path: tests/modules/tools/test_user_tool_contracts.py
Role: Unit tests for tenant tool payload normalization and schema fingerprinting.
Used By:
 - pytest
Depends On:
 - src/tools/user_tool_contracts.py
Notes:
 - Validates OpenAI-style payloads and canonical handler conventions.
"""

from __future__ import annotations

import pytest

from src.tools.user_tool_contracts import (
    SANDBOX_CPU_BUDGET_MS_KEY,
    SANDBOX_CPU_BUDGET_MS_MAX,
    SANDBOX_LIMITS_METADATA_KEY,
    SANDBOX_MEMORY_BUDGET_MB_KEY,
    default_handler_ref,
    normalize_manifest_metadata,
    normalize_tool_payload,
    parse_sandbox_limits,
    schema_fingerprint,
)


def test_normalize_openai_function_wrapper_payload() -> None:
    payload = {
        "type": "function",
        "function": {
            "name": "calculate_result",
            "description": "Math tool",
            "parameters": {"type": "object", "properties": {"x": {"type": "number"}}},
        },
    }
    normalized = normalize_tool_payload(payload)
    assert normalized.name == "calculate_result"
    assert normalized.description == "Math tool"
    assert normalized.parameters_schema["type"] == "object"


def test_normalize_direct_function_payload() -> None:
    payload = {
        "name": "calculate_result",
        "description": "Math tool",
        "parameters": {"type": "object", "properties": {"x": {"type": "number"}}},
    }
    normalized = normalize_tool_payload(payload)
    assert normalized.name == "calculate_result"
    assert normalized.parameters_schema["properties"]["x"]["type"] == "number"


def test_normalize_raw_schema_payload_without_name() -> None:
    payload = {"type": "object", "properties": {"operation": {"type": "string"}}}
    normalized = normalize_tool_payload(payload)
    assert normalized.name == ""
    assert normalized.parameters_schema == payload


def test_normalize_tool_payload_rejects_non_object() -> None:
    with pytest.raises(ValueError, match="JSON object"):
        normalize_tool_payload([])  # type: ignore[arg-type]


def test_normalize_invalid_wrapper_raises() -> None:
    payload = {"type": "function", "function": "not-an-object"}
    try:
        normalize_tool_payload(payload)  # pragma: no cover - explicit assert path below
    except ValueError as exc:
        assert "must include object field 'function'" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("Expected ValueError")


def test_default_handler_ref_uses_standard_module() -> None:
    assert default_handler_ref("calculate_result") == "src.tools.user_tools:calculate_result"


def test_schema_fingerprint_stable_across_key_order() -> None:
    a = {"type": "object", "properties": {"x": {"type": "number"}, "y": {"type": "number"}}}
    b = {"properties": {"y": {"type": "number"}, "x": {"type": "number"}}, "type": "object"}
    assert schema_fingerprint(a) == schema_fingerprint(b)


def test_parse_sandbox_limits_accepts_valid_values() -> None:
    metadata = {
        SANDBOX_LIMITS_METADATA_KEY: {
            SANDBOX_CPU_BUDGET_MS_KEY: 5000,
            SANDBOX_MEMORY_BUDGET_MB_KEY: 256,
        }
    }
    limits = parse_sandbox_limits(metadata)
    assert limits is not None
    assert limits.cpu_budget_ms == 5000
    assert limits.memory_budget_mb == 256


def test_parse_sandbox_limits_rejects_non_object_metadata() -> None:
    with pytest.raises(ValueError, match="metadata must be an object"):
        parse_sandbox_limits("bad")  # type: ignore[arg-type]


def test_parse_sandbox_limits_rejects_non_object_limits_block() -> None:
    with pytest.raises(ValueError, match="must be an object"):
        parse_sandbox_limits({SANDBOX_LIMITS_METADATA_KEY: "nope"})


def test_parse_sandbox_limits_rejects_out_of_range_cpu_budget() -> None:
    metadata = {SANDBOX_LIMITS_METADATA_KEY: {SANDBOX_CPU_BUDGET_MS_KEY: SANDBOX_CPU_BUDGET_MS_MAX + 1}}
    with pytest.raises(ValueError, match="cpu_budget_ms must be between"):
        parse_sandbox_limits(metadata)


def test_parse_sandbox_limits_rejects_invalid_values() -> None:
    metadata = {
        SANDBOX_LIMITS_METADATA_KEY: {
            SANDBOX_MEMORY_BUDGET_MB_KEY: "bad",
        }
    }
    with pytest.raises(ValueError):
        parse_sandbox_limits(metadata)


def test_normalize_manifest_metadata_canonicalizes_limit_fields() -> None:
    metadata = {
        SANDBOX_LIMITS_METADATA_KEY: {
            SANDBOX_CPU_BUDGET_MS_KEY: "7000",
            SANDBOX_MEMORY_BUDGET_MB_KEY: "128",
        }
    }
    normalized = normalize_manifest_metadata(metadata)
    assert normalized[SANDBOX_LIMITS_METADATA_KEY][SANDBOX_CPU_BUDGET_MS_KEY] == 7000
    assert normalized[SANDBOX_LIMITS_METADATA_KEY][SANDBOX_MEMORY_BUDGET_MB_KEY] == 128
