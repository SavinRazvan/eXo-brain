"""
File: test_sandbox_policy.py
Path: tests/modules/tools/test_sandbox_policy.py
Role: Unit tests for hosted sandbox runtime policy resolution.
Used By:
 - pytest
Depends On:
 - src/tools/sandbox/policy.py
 - src/schemas/tool_io.py
 - src/tools/registry.py
Notes:
 - Covers invalid sandbox_timeout_ms coercion and tenant defaulting.
"""

from __future__ import annotations

from src.schemas.tool_io import ToolCallContext
from src.tools.registry import ToolDescriptor
from src.tools.sandbox.policy import SandboxRuntimePolicy


def test_resolve_timeout_falls_back_when_metadata_not_int() -> None:
    policy = SandboxRuntimePolicy()
    descriptor = ToolDescriptor(
        name="t",
        handler=lambda: None,
        timeout_ms=5000,
        metadata={"sandbox_timeout_ms": "not-an-int"},
    )
    assert policy.resolve_timeout_ms(descriptor) == 5000


def test_resolve_tenant_id_defaults_when_blank() -> None:
    policy = SandboxRuntimePolicy()
    call = ToolCallContext(
        schema_version="1.0",
        call_id="c1",
        session_id="s1",
        run_id="r1",
        job_id="j1",
        task_id="t1",
        agent_id="a1",
        provider_id="openai",
        tool_name="x",
        arguments={},
        tenant_id="   ",
    )
    assert policy.resolve_tenant_id(call) == "default"
