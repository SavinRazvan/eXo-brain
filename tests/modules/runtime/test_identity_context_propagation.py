"""
File: test_identity_context_propagation.py
Path: tests/modules/runtime/test_identity_context_propagation.py
Role: Integration test for identity propagation into runtime tool-intent context.
Used By:
 - pytest
Depends On:
 - src/runtime/openai_agents_runtime.py
 - src/schemas/events.py
Notes:
 - Verifies identity fields are attached to tool call context for policy decisions.
"""

import asyncio

from src.runtime.openai_agents_runtime import OpenAIAgentsRuntimeAdapter
from src.schemas.events import RuntimeEventType


def test_openai_adapter_attaches_identity_to_tool_call_context() -> None:
    adapter = OpenAIAgentsRuntimeAdapter()

    async def collect() -> list[tuple[str, list[str]]]:
        output: list[tuple[str, list[str]]] = []
        async for event in adapter.run_turn(
            session_id="sess_identity",
            user_input="trigger tool",
            context={
                "run_id": "run_identity",
                "planned_tool_call": {"tool_name": "noop", "arguments": {}},
                "identity": {"subject": "user_identity", "roles": ["operator", "auditor"]},
            },
        ):
            if event.event_type == RuntimeEventType.TOOL_INTENT and event.tool_call is not None:
                output.append((event.tool_call.identity_subject, list(event.tool_call.identity_roles)))
        return output

    calls = asyncio.run(collect())
    assert calls == [("user_identity", ["operator", "auditor"])]
