"""
File: test_orchestrator_agent_handoff.py
Path: tests/integration/test_orchestrator_agent_handoff.py
Role: Integration tests for orchestrator-side agent handoff routing with registry constraints.
Used By:
 - pytest
Depends On:
 - src/agents/contracts.py
 - src/agents/plugin_contract.py
 - src/agents/plugin_manager.py
 - src/agents/registry.py
 - src/core/orchestrator.py
 - src/runtime/openai_agents_runtime.py
 - src/tools/registry.py
 - src/tools/executor.py
 - src/policies/middleware.py
 - src/schemas/events.py
 - src/schemas/tool_io.py
Notes:
 - Verifies handoff routing, fallback behavior, and fail-closed validation errors.
"""

from __future__ import annotations

import asyncio
from typing import Any

from src.agents.contracts import AgentCapabilityTag, AgentSpec, HandoffFallbackPolicy, HandoffRoute
from src.agents.plugin_contract import AgentPlugin, AgentPluginManifest
from src.agents.plugin_manager import AgentPluginManager
from src.agents.registry import AgentRegistry
from src.core.orchestrator import Orchestrator
from src.policies.middleware import DeterministicFirstPolicyMiddleware, PolicyMiddleware
from src.runtime.openai_agents_runtime import OpenAIAgentsRuntimeAdapter
from src.schemas.events import RuntimeEvent, RuntimeEventType
from src.schemas.tool_io import (
    PolicyAction,
    PolicyDecision,
    ToolCallContext,
    ToolExecutionMode,
    ToolResult,
)
from src.tools.executor import DeterministicToolExecutor
from src.tools.registry import ToolDescriptor, ToolRegistry


class RecordingAllowPolicy(PolicyMiddleware):
    def __init__(self) -> None:
        self.seen_agent_ids: list[str] = []

    def before_tool_call(self, context: ToolCallContext) -> PolicyDecision:
        self.seen_agent_ids.append(context.agent_id)
        return PolicyDecision(
            schema_version="1.0",
            decision=PolicyAction.ALLOW,
            reason_code="ALLOW_FOR_TEST",
            message="Allowed for integration test.",
            enforced_mode=ToolExecutionMode.DETERMINISTIC,
        )

    def after_tool_call(self, result: ToolResult) -> ToolResult:
        return result

    def before_output(self, output: dict[str, Any]) -> dict[str, Any]:
        return output


async def _collect_events(orchestrator: Orchestrator, context: dict[str, Any]) -> list[RuntimeEvent]:
    events: list[RuntimeEvent] = []
    async for event in orchestrator.run_turn(
        session_id="sess_handoff",
        user_input="route-tool",
        context=context,
    ):
        events.append(event)
    return events


def _base_registry() -> AgentRegistry:
    registry = AgentRegistry()
    registry.register(
        AgentSpec(
            agent_id="agent_router",
            role="router",
            capability_tags={AgentCapabilityTag.WORKFLOW_ROUTING},
        )
    )
    registry.register(
        AgentSpec(
            agent_id="agent_reviewer",
            role="reviewer",
            capability_tags={AgentCapabilityTag.REVIEW, AgentCapabilityTag.TOOL_USE},
        )
    )
    registry.add_handoff_route(
        HandoffRoute(
            source_role="router",
            target_role="reviewer",
            reason="review-stage",
            required_target_capabilities={AgentCapabilityTag.REVIEW},
        )
    )
    return registry


def _orchestrator_with_registry(
    registry: AgentRegistry,
    policy: PolicyMiddleware,
) -> Orchestrator:
    tools = ToolRegistry()
    tools.register(ToolDescriptor(name="echo_tool", handler=lambda text: text))
    return Orchestrator(
        runtime_adapter=OpenAIAgentsRuntimeAdapter(),
        policy_middleware=policy,
        tool_executor=DeterministicToolExecutor(
            registry=tools,
            policy=DeterministicFirstPolicyMiddleware(),
        ),
        agent_registry=registry,
    )


def test_orchestrator_handoff_routes_to_explicit_target_role() -> None:
    registry = _base_registry()
    policy = RecordingAllowPolicy()
    orchestrator = _orchestrator_with_registry(registry=registry, policy=policy)
    context = {
        "run_id": "run_handoff_role",
        "job_id": "job_handoff_role",
        "task_id": "task_handoff_role",
        "agent_id": "agent_router",
        "handoff": {"target_role": "reviewer", "reason": "needs-review"},
        "planned_tool_call": {
            "call_id": "tc_handoff_role",
            "tool_name": "echo_tool",
            "arguments": {"text": "payload"},
        },
    }

    events = asyncio.run(_collect_events(orchestrator, context))
    assert policy.seen_agent_ids == ["agent_reviewer"]
    assert RuntimeEventType.RUN_COMPLETE in [event.event_type for event in events]


def test_orchestrator_handoff_selects_target_by_required_capability() -> None:
    registry = _base_registry()
    policy = RecordingAllowPolicy()
    orchestrator = _orchestrator_with_registry(registry=registry, policy=policy)
    context = {
        "run_id": "run_handoff_capability",
        "job_id": "job_handoff_capability",
        "task_id": "task_handoff_capability",
        "agent_id": "agent_router",
        "handoff": {"required_capability": "review", "reason": "auto-pick-reviewer"},
        "planned_tool_call": {
            "call_id": "tc_handoff_capability",
            "tool_name": "echo_tool",
            "arguments": {"text": "payload"},
        },
    }

    events = asyncio.run(_collect_events(orchestrator, context))
    assert policy.seen_agent_ids == ["agent_reviewer"]
    assert RuntimeEventType.RUN_COMPLETE in [event.event_type for event in events]


def test_orchestrator_handoff_route_denied_emits_error_event() -> None:
    registry = _base_registry()
    registry.register(
        AgentSpec(
            agent_id="agent_worker",
            role="worker",
            capability_tags={AgentCapabilityTag.BACKGROUND_EXECUTION},
        )
    )
    policy = RecordingAllowPolicy()
    orchestrator = _orchestrator_with_registry(registry=registry, policy=policy)
    context = {
        "run_id": "run_handoff_denied",
        "job_id": "job_handoff_denied",
        "task_id": "task_handoff_denied",
        "agent_id": "agent_router",
        "handoff": {"target_role": "worker", "reason": "disallowed-route"},
    }

    events = asyncio.run(_collect_events(orchestrator, context))
    assert policy.seen_agent_ids == []
    assert len(events) == 1
    assert events[0].event_type == RuntimeEventType.ERROR
    assert events[0].payload["code"] == "ORCH_HANDOFF_ROUTE_DENIED"


def test_orchestrator_handoff_uses_fallback_after_primary_plugin_unload() -> None:
    registry = AgentRegistry()
    registry.register(
        AgentSpec(
            agent_id="agent_router",
            role="router",
            capability_tags={AgentCapabilityTag.WORKFLOW_ROUTING},
        )
    )
    registry.register(
        AgentSpec(
            agent_id="agent_backup_reviewer_a",
            role="backup_reviewer_a",
            capability_tags={AgentCapabilityTag.REVIEW, AgentCapabilityTag.TOOL_USE},
        )
    )
    registry.register(
        AgentSpec(
            agent_id="agent_backup_reviewer_b",
            role="backup_reviewer_b",
            capability_tags={AgentCapabilityTag.REVIEW, AgentCapabilityTag.TOOL_USE},
        )
    )
    registry.add_handoff_route(
        HandoffRoute(
            source_role="router",
            target_role="backup_reviewer_a",
            reason="backup-review-stage",
            required_target_capabilities={AgentCapabilityTag.REVIEW},
        )
    )
    registry.add_handoff_route(
        HandoffRoute(
            source_role="router",
            target_role="backup_reviewer_b",
            reason="backup-review-stage",
            required_target_capabilities={AgentCapabilityTag.REVIEW},
        )
    )
    plugin_manager = AgentPluginManager(registry=registry, core_major_version=1)
    plugin_manager.load_plugin(
        AgentPlugin(
            manifest=AgentPluginManifest(
                plugin_id="review-primary",
                version="1.0.0",
                compatible_core_major=1,
            ),
            agents=[
                AgentSpec(
                    agent_id="agent_reviewer",
                    role="reviewer",
                    capability_tags={AgentCapabilityTag.REVIEW, AgentCapabilityTag.TOOL_USE},
                )
            ],
            routes=[
                HandoffRoute(
                    source_role="router",
                    target_role="reviewer",
                    reason="review-stage",
                    required_target_capabilities={AgentCapabilityTag.REVIEW},
                )
            ],
            fallback_policies=[
                HandoffFallbackPolicy(
                    source_role="router",
                    target_role="reviewer",
                    fallback_target_roles=["backup_reviewer_a", "backup_reviewer_b"],
                    target_role_priorities={
                        "backup_reviewer_a": 10,
                        "backup_reviewer_b": 100,
                    },
                )
            ],
        )
    )
    plugin_manager.unload_plugin("review-primary")

    policy = RecordingAllowPolicy()
    orchestrator = _orchestrator_with_registry(registry=registry, policy=policy)
    context = {
        "run_id": "run_handoff_fallback",
        "job_id": "job_handoff_fallback",
        "task_id": "task_handoff_fallback",
        "agent_id": "agent_router",
        "handoff": {"target_role": "reviewer", "reason": "prefer-primary-reviewer"},
        "planned_tool_call": {
            "call_id": "tc_handoff_fallback",
            "tool_name": "echo_tool",
            "arguments": {"text": "payload"},
        },
    }

    events = asyncio.run(_collect_events(orchestrator, context))
    assert policy.seen_agent_ids == ["agent_backup_reviewer_b"]
    assert RuntimeEventType.RUN_COMPLETE in [event.event_type for event in events]
