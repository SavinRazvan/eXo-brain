"""
File: test_agent_registry.py
Path: tests/unit/test_agent_registry.py
Role: Unit tests for agent registration, capability lookup, and role handoff routing.
Used By:
 - pytest
Depends On:
 - src/agents/contracts.py
 - src/agents/registry.py
Notes:
 - Validates explicit handoff gates before integrating routes into orchestrator logic.
"""

from __future__ import annotations

import pytest

from src.agents.contracts import AgentCapabilityTag, AgentSpec, HandoffRoute
from src.agents.registry import AgentRegistry


def _build_registry() -> AgentRegistry:
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
    registry.register(
        AgentSpec(
            agent_id="agent_worker",
            role="worker",
            capability_tags={AgentCapabilityTag.TOOL_USE, AgentCapabilityTag.BACKGROUND_EXECUTION},
        )
    )
    return registry


def test_register_and_get_by_role() -> None:
    registry = _build_registry()

    reviewer = registry.get_by_role("reviewer")
    assert reviewer.agent_id == "agent_reviewer"
    assert reviewer.has_capability(AgentCapabilityTag.REVIEW)


def test_duplicate_agent_id_is_rejected() -> None:
    registry = AgentRegistry()
    registry.register(AgentSpec(agent_id="agent_1", role="router"))

    with pytest.raises(ValueError, match="already registered"):
        registry.register(AgentSpec(agent_id="agent_1", role="reviewer"))


def test_add_handoff_route_requires_known_roles() -> None:
    registry = _build_registry()
    with pytest.raises(ValueError, match="unknown source role"):
        registry.add_handoff_route(
            HandoffRoute(
                source_role="planner",
                target_role="reviewer",
                reason="handoff-for-review",
            )
        )


def test_can_handoff_with_required_capability() -> None:
    registry = _build_registry()
    registry.add_handoff_route(
        HandoffRoute(
            source_role="router",
            target_role="reviewer",
            reason="requires-review",
            required_target_capabilities={AgentCapabilityTag.REVIEW},
        )
    )

    assert registry.can_handoff("agent_router", "agent_reviewer") is True
    assert registry.can_handoff("agent_router", "agent_worker") is False


def test_route_rejects_missing_required_capability() -> None:
    registry = _build_registry()
    with pytest.raises(ValueError, match="required capabilities"):
        registry.add_handoff_route(
            HandoffRoute(
                source_role="router",
                target_role="worker",
                reason="needs-retrieval-first",
                required_target_capabilities={AgentCapabilityTag.RETRIEVAL},
            )
        )


def test_handoff_targets_support_optional_capability_filter() -> None:
    registry = _build_registry()
    registry.add_handoff_route(
        HandoffRoute(
            source_role="router",
            target_role="reviewer",
            reason="review-stage",
            required_target_capabilities={AgentCapabilityTag.REVIEW},
        )
    )
    registry.add_handoff_route(
        HandoffRoute(
            source_role="router",
            target_role="worker",
            reason="execution-stage",
            required_target_capabilities={AgentCapabilityTag.BACKGROUND_EXECUTION},
        )
    )

    all_targets = registry.handoff_targets("agent_router")
    review_targets = registry.handoff_targets("agent_router", required_capability=AgentCapabilityTag.REVIEW)

    assert [target.agent_id for target in all_targets] == ["agent_reviewer", "agent_worker"]
    assert [target.agent_id for target in review_targets] == ["agent_reviewer"]
