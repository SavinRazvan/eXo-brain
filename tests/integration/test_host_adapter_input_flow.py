"""
File: test_host_adapter_input_flow.py
Path: tests/integration/test_host_adapter_input_flow.py
Role: Integration test for host adapter input handoff into orchestration core.
Used By:
 - pytest
Depends On:
 - src/integration/host_adapter.py
 - src/core/orchestrator.py
 - src/core/session_context.py
 - src/runtime/openai_agents_runtime.py
 - src/policies/middleware.py
 - src/tools/registry.py
 - src/tools/executor.py
Notes:
 - Confirms host boundary receives input and streams normalized runtime events.
"""

from __future__ import annotations

import asyncio

from src.core.orchestrator import Orchestrator
from src.core.session_context import SessionContext
from src.integration.host_adapter import OrchestratorHostAdapter
from src.policies.middleware import DeterministicFirstPolicyMiddleware
from src.runtime.openai_agents_runtime import OpenAIAgentsRuntimeAdapter
from src.schemas.events import RuntimeEventType
from src.tools.executor import DeterministicToolExecutor
from src.tools.registry import ToolDescriptor, ToolRegistry


def test_host_adapter_receives_input_and_streams_events() -> None:
    async def scenario() -> None:
        registry = ToolRegistry()
        registry.register(ToolDescriptor(name="noop", handler=lambda: "ok"))
        policy = DeterministicFirstPolicyMiddleware()
        orchestrator = Orchestrator(
            runtime_adapter=OpenAIAgentsRuntimeAdapter(),
            policy_middleware=policy,
            tool_executor=DeterministicToolExecutor(registry=registry, policy=policy),
        )
        host = OrchestratorHostAdapter(orchestrator=orchestrator)
        session = SessionContext(
            session_id="sess_host",
            run_id="run_host",
            job_id="job_host",
            task_id="task_host",
            agent_id="agent_host",
            provider_id="openai",
            correlation_id="corr_host",
            metadata={"channel": "test"},
        )

        events = []
        async for event in host.submit_turn(session=session, user_input="hello host"):
            events.append(event)

        event_types = [event.event_type for event in events]
        assert RuntimeEventType.OUTPUT_DELTA in event_types
        assert RuntimeEventType.RUN_COMPLETE in event_types

    asyncio.run(scenario())
