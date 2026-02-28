"""
File: test_deterministic_tool_replay.py
Path: tests/modules/policies/test_deterministic_tool_replay.py
Role: Replay test for deterministic tool execution output stability.
Used By:
 - pytest
Depends On:
 - src/tools/executor.py
 - src/tools/registry.py
 - src/policies/middleware.py
 - src/schemas/tool_io.py
Notes:
 - Guards deterministic side-effect path behavior.
"""

from src.policies.middleware import DeterministicFirstPolicyMiddleware
from src.schemas.tool_io import ToolCallContext, ToolStatus
from src.tools.executor import DeterministicToolExecutor
from src.tools.registry import ToolDescriptor, ToolRegistry


def test_deterministic_tool_replay_produces_stable_result() -> None:
    registry = ToolRegistry()
    registry.register(ToolDescriptor(name="add", handler=lambda a, b: a + b))
    executor = DeterministicToolExecutor(registry=registry, policy=DeterministicFirstPolicyMiddleware())
    call = ToolCallContext(
        schema_version="1.0",
        call_id="tc_replay",
        session_id="sess_1",
        run_id="run_1",
        job_id="job_1",
        task_id="task_1",
        agent_id="agent_1",
        provider_id="openai",
        tool_name="add",
        arguments={"a": 3, "b": 4},
    )
    first = executor.execute(call)
    second = executor.execute(call)
    assert first.status == ToolStatus.SUCCESS
    assert second.status == ToolStatus.SUCCESS
    assert first.result == second.result == {"value": 7}

