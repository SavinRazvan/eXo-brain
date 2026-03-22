"""
File: test_policy_middleware_abstract.py
Path: tests/modules/policies/test_policy_middleware_abstract.py
Role: Coverage for abstract PolicyMiddleware default method bodies.
Used By:
 - pytest
Depends On:
 - src/policies/middleware.py
 - src/schemas/tool_io.py
Notes:
 - Uses __new__ to invoke NotImplementedError paths without a concrete subclass.
"""

from __future__ import annotations

import pytest

from src.policies.middleware import PolicyMiddleware
from src.schemas.tool_io import ToolCallContext, ToolResult, ToolStatus


def _minimal_context() -> ToolCallContext:
    return ToolCallContext(
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
    )


def test_policy_middleware_abstract_methods_raise_not_implemented() -> None:
    saved_abstract = PolicyMiddleware.__abstractmethods__
    PolicyMiddleware.__abstractmethods__ = frozenset()
    try:
        base = PolicyMiddleware.__new__(PolicyMiddleware)
    finally:
        PolicyMiddleware.__abstractmethods__ = saved_abstract

    ctx = _minimal_context()
    dummy_result = ToolResult(
        schema_version="1.0",
        call_id="c1",
        tool_name="x",
        status=ToolStatus.SUCCESS,
    )
    with pytest.raises(NotImplementedError):
        PolicyMiddleware.before_tool_call(base, ctx)
    with pytest.raises(NotImplementedError):
        PolicyMiddleware.after_tool_call(base, dummy_result)
    with pytest.raises(NotImplementedError):
        PolicyMiddleware.before_output(base, {})
