"""
File: orchestrator.py
Path: src/core/orchestrator.py
Role: Orchestrates one-turn execution across runtime adapter, policies, and tool runtime.
Used By:
 - integration host adapters (future)
 - tests/integration/test_background_agent_pipeline.py (future)
Depends On:
 - src/runtime/runtime_adapter.py
 - src/runtime/mode_selector.py
 - src/policies/middleware.py
 - src/tools/executor.py
 - src/schemas/events.py
 - src/schemas/tool_io.py
Notes:
 - Core must remain provider-neutral and avoid provider SDK imports.
"""

from __future__ import annotations

from typing import AsyncIterator

from src.policies.middleware import PolicyMiddleware
from src.runtime.mode_selector import select_execution_mode
from src.runtime.runtime_adapter import RuntimeAdapter
from src.schemas.events import RuntimeEvent, RuntimeEventType
from src.schemas.tool_io import PolicyAction, ToolExecutionMode
from src.tools.executor import DeterministicToolExecutor


class Orchestrator:
    def __init__(
        self,
        runtime_adapter: RuntimeAdapter,
        policy_middleware: PolicyMiddleware,
        tool_executor: DeterministicToolExecutor,
    ) -> None:
        self._runtime_adapter = runtime_adapter
        self._policy = policy_middleware
        self._tool_executor = tool_executor

    async def run_turn(
        self,
        session_id: str,
        user_input: str,
        context: dict,
    ) -> AsyncIterator[RuntimeEvent]:
        await self._runtime_adapter.start_session(session_id=session_id, metadata=context.get("session_metadata"))

        async for event in self._runtime_adapter.run_turn(session_id=session_id, user_input=user_input, context=context):
            if event.event_type != RuntimeEventType.TOOL_INTENT or event.tool_call is None:
                yield event
                continue

            decision = self._policy.before_tool_call(event.tool_call)
            if decision.decision != PolicyAction.ALLOW:
                blocked = self._tool_executor.execute(event.tool_call)
                async for follow_up in self._runtime_adapter.submit_tool_results(
                    session_id=session_id,
                    run_id=event.run_id,
                    tool_results=[blocked],
                ):
                    yield follow_up
                continue

            mode = select_execution_mode(
                tool_call=event.tool_call,
                capability_map=self._runtime_adapter.get_capabilities(),
                policy_decision=decision,
            )
            if mode == ToolExecutionMode.DETERMINISTIC:
                result = self._tool_executor.execute(event.tool_call)
                async for follow_up in self._runtime_adapter.submit_tool_results(
                    session_id=session_id,
                    run_id=event.run_id,
                    tool_results=[result],
                ):
                    yield follow_up
            else:
                # Provider-native execution path is left to adapter behavior.
                yield event
