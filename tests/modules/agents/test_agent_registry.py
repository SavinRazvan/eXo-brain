"""
File: test_agent_registry.py
Path: tests/modules/agents/test_agent_registry.py
Role: Unit tests for agent registration, capability lookup, and role handoff routing.
Used By:
 - pytest
Depends On:
 - src/agents/contracts.py
 - src/agents/registry.py
Notes:
 - Validates explicit handoff gates, fallback routing, and unregister behavior.
"""

from __future__ import annotations

import pytest

from src.agents.contracts import AgentCapabilityTag, AgentSpec, HandoffFallbackPolicy, HandoffRoute
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


def test_resolve_handoff_target_uses_fallback_when_primary_unavailable() -> None:
    registry = _build_registry()
    registry.register(
        AgentSpec(
            agent_id="agent_backup_reviewer",
            role="backup_reviewer",
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
    registry.add_handoff_route(
        HandoffRoute(
            source_role="router",
            target_role="backup_reviewer",
            reason="fallback-review-stage",
            required_target_capabilities={AgentCapabilityTag.REVIEW},
        )
    )
    registry.set_handoff_fallback_policy(
        HandoffFallbackPolicy(
            source_role="router",
            target_role="reviewer",
            fallback_target_roles=["backup_reviewer"],
        )
    )
    registry.unregister("agent_reviewer")

    resolved = registry.resolve_handoff_target(
        source_agent_id="agent_router",
        target_role="reviewer",
        required_capability=AgentCapabilityTag.REVIEW,
    )
    assert resolved is not None
    assert resolved.agent_id == "agent_backup_reviewer"


def test_resolve_handoff_target_prefers_highest_priority_fallback() -> None:
    registry = _build_registry()
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
            target_role="reviewer",
            reason="review-stage",
            required_target_capabilities={AgentCapabilityTag.REVIEW},
        )
    )
    registry.add_handoff_route(
        HandoffRoute(
            source_role="router",
            target_role="backup_reviewer_a",
            reason="fallback-review-stage",
            required_target_capabilities={AgentCapabilityTag.REVIEW},
        )
    )
    registry.add_handoff_route(
        HandoffRoute(
            source_role="router",
            target_role="backup_reviewer_b",
            reason="fallback-review-stage",
            required_target_capabilities={AgentCapabilityTag.REVIEW},
        )
    )
    registry.set_handoff_fallback_policy(
        HandoffFallbackPolicy(
            source_role="router",
            target_role="reviewer",
            fallback_target_roles=["backup_reviewer_a", "backup_reviewer_b"],
            target_role_priorities={"backup_reviewer_a": 10, "backup_reviewer_b": 100},
        )
    )
    registry.unregister("agent_reviewer")

    resolved = registry.resolve_handoff_target(
        source_agent_id="agent_router",
        target_role="reviewer",
        required_capability=AgentCapabilityTag.REVIEW,
    )
    assert resolved is not None
    assert resolved.agent_id == "agent_backup_reviewer_b"


def test_resolve_handoff_target_tie_breaks_by_agent_id() -> None:
    registry = _build_registry()
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
            target_role="reviewer",
            reason="review-stage",
            required_target_capabilities={AgentCapabilityTag.REVIEW},
        )
    )
    registry.add_handoff_route(
        HandoffRoute(
            source_role="router",
            target_role="backup_reviewer_a",
            reason="fallback-review-stage",
            required_target_capabilities={AgentCapabilityTag.REVIEW},
        )
    )
    registry.add_handoff_route(
        HandoffRoute(
            source_role="router",
            target_role="backup_reviewer_b",
            reason="fallback-review-stage",
            required_target_capabilities={AgentCapabilityTag.REVIEW},
        )
    )
    registry.set_handoff_fallback_policy(
        HandoffFallbackPolicy(
            source_role="router",
            target_role="reviewer",
            fallback_target_roles=["backup_reviewer_b", "backup_reviewer_a"],
            target_role_priorities={"backup_reviewer_a": 100, "backup_reviewer_b": 100},
        )
    )
    registry.unregister("agent_reviewer")

    resolved = registry.resolve_handoff_target(
        source_agent_id="agent_router",
        target_role="reviewer",
        required_capability=AgentCapabilityTag.REVIEW,
    )
    assert resolved is not None
    assert resolved.agent_id == "agent_backup_reviewer_a"


def test_fallback_priority_map_rejects_unknown_role() -> None:
    registry = _build_registry()
    with pytest.raises(ValueError, match="unknown target role"):
        registry.set_handoff_fallback_policy(
            HandoffFallbackPolicy(
                source_role="router",
                target_role="reviewer",
                fallback_target_roles=["worker"],
                target_role_priorities={"missing_role": 5},
            )
        )


def test_unregister_removes_agent_and_associated_routes() -> None:
    registry = _build_registry()
    registry.add_handoff_route(
        HandoffRoute(
            source_role="router",
            target_role="worker",
            reason="execution-stage",
            required_target_capabilities={AgentCapabilityTag.BACKGROUND_EXECUTION},
        )
    )

    registry.unregister("agent_worker")

    with pytest.raises(KeyError, match="Unknown agent_id"):
        registry.get("agent_worker")
    assert registry.resolve_handoff_target("agent_router", target_role="worker") is None


def test_register_rejects_blank_agent_id() -> None:
    registry = AgentRegistry()
    with pytest.raises(ValueError, match="agent_id"):
        registry.register(AgentSpec(agent_id="   ", role="r1"))


def test_register_rejects_blank_role() -> None:
    registry = AgentRegistry()
    with pytest.raises(ValueError, match="role"):
        registry.register(AgentSpec(agent_id="a1", role="  "))


def test_register_rejects_duplicate_role_binding() -> None:
    registry = AgentRegistry()
    registry.register(AgentSpec(agent_id="a1", role="shared"))
    with pytest.raises(ValueError, match="Role 'shared'"):
        registry.register(AgentSpec(agent_id="a2", role="shared"))


def test_get_unknown_agent_raises() -> None:
    registry = AgentRegistry()
    with pytest.raises(KeyError, match="Unknown agent_id"):
        registry.get("missing")


def test_get_by_role_unknown_raises() -> None:
    registry = AgentRegistry()
    with pytest.raises(KeyError, match="Unknown role"):
        registry.get_by_role("ghost")


def test_add_handoff_route_rejects_unknown_target_role() -> None:
    registry = _build_registry()
    with pytest.raises(ValueError, match="unknown target role"):
        registry.add_handoff_route(
            HandoffRoute(source_role="router", target_role="nope", reason="x")
        )


def test_set_handoff_fallback_rejects_unknown_source_role() -> None:
    registry = _build_registry()
    with pytest.raises(ValueError, match="unknown source role"):
        registry.set_handoff_fallback_policy(
            HandoffFallbackPolicy(source_role="nope", target_role="reviewer", fallback_target_roles=["worker"])
        )


def test_set_handoff_fallback_rejects_unknown_policy_target_role() -> None:
    registry = _build_registry()
    with pytest.raises(ValueError, match="unknown target role"):
        registry.set_handoff_fallback_policy(
            HandoffFallbackPolicy(source_role="router", target_role="nope", fallback_target_roles=["worker"])
        )


def test_find_with_capability_filters_agents() -> None:
    registry = _build_registry()
    found = registry.find_with_capability(AgentCapabilityTag.REVIEW)
    assert {a.agent_id for a in found} == {"agent_reviewer"}


def test_resolve_handoff_target_without_target_role_returns_first_sorted() -> None:
    registry = _build_registry()
    registry.add_handoff_route(
        HandoffRoute(
            source_role="router",
            target_role="worker",
            reason="exec",
            required_target_capabilities={AgentCapabilityTag.BACKGROUND_EXECUTION},
        )
    )
    resolved = registry.resolve_handoff_target("agent_router", target_role=None)
    assert resolved is not None
    assert resolved.agent_id == "agent_worker"


def test_resolve_handoff_target_returns_none_when_no_routes() -> None:
    registry = _build_registry()
    assert registry.resolve_handoff_target("agent_router", target_role=None) is None


def test_set_handoff_fallback_skips_blank_duplicate_and_same_as_target() -> None:
    registry = _build_registry()
    registry.set_handoff_fallback_policy(
        HandoffFallbackPolicy(
            source_role="router",
            target_role="reviewer",
            fallback_target_roles=["", "reviewer", "worker", "worker"],
        )
    )
    policies = registry.list_fallback_policies()
    assert policies[0].fallback_target_roles == ["worker"]


def test_resolve_handoff_fallback_skips_duplicate_role_entries() -> None:
    registry = _build_registry()
    registry.register(
        AgentSpec(
            agent_id="agent_backup",
            role="backup",
            capability_tags={AgentCapabilityTag.REVIEW, AgentCapabilityTag.TOOL_USE},
        )
    )
    registry.add_handoff_route(
        HandoffRoute(
            source_role="router",
            target_role="reviewer",
            reason="r1",
            required_target_capabilities={AgentCapabilityTag.REVIEW},
        )
    )
    registry.add_handoff_route(
        HandoffRoute(
            source_role="router",
            target_role="backup",
            reason="r2",
            required_target_capabilities={AgentCapabilityTag.REVIEW},
        )
    )
    registry.set_handoff_fallback_policy(
        HandoffFallbackPolicy(
            source_role="router",
            target_role="reviewer",
            fallback_target_roles=["backup", "backup"],
        )
    )
    registry.unregister("agent_reviewer")
    resolved = registry.resolve_handoff_target("agent_router", target_role="reviewer")
    assert resolved is not None
    assert resolved.agent_id == "agent_backup"


def test_list_routes_returns_registered_route_objects() -> None:
    registry = _build_registry()
    route = HandoffRoute(
        source_role="router",
        target_role="reviewer",
        reason="r",
        required_target_capabilities={AgentCapabilityTag.REVIEW},
    )
    registry.add_handoff_route(route)
    routes = registry.list_routes()
    assert len(routes) == 1
    assert routes[0] is route


def test_set_handoff_fallback_priorities_skip_blank_role_keys() -> None:
    registry = _build_registry()
    registry.set_handoff_fallback_policy(
        HandoffFallbackPolicy(
            source_role="router",
            target_role="reviewer",
            fallback_target_roles=["worker"],
            target_role_priorities={"": 1, "worker": 5},
        )
    )
    policies = registry.list_fallback_policies()
    assert policies[0].target_role_priorities == {"worker": 5}


def test_handoff_targets_skips_routes_for_other_source_roles() -> None:
    registry = _build_registry()
    registry.register(
        AgentSpec(agent_id="agent_planner", role="planner", capability_tags={AgentCapabilityTag.TOOL_USE})
    )
    registry.add_handoff_route(
        HandoffRoute(
            source_role="router",
            target_role="reviewer",
            reason="r1",
            required_target_capabilities={AgentCapabilityTag.REVIEW},
        )
    )
    registry.add_handoff_route(
        HandoffRoute(
            source_role="planner",
            target_role="worker",
            reason="r2",
            required_target_capabilities={AgentCapabilityTag.BACKGROUND_EXECUTION},
        )
    )
    targets = registry.handoff_targets("agent_router")
    assert [t.agent_id for t in targets] == ["agent_reviewer"]


def test_resolve_handoff_skips_fallback_role_without_registered_agent() -> None:
    registry = _build_registry()
    registry.add_handoff_route(
        HandoffRoute(
            source_role="router",
            target_role="reviewer",
            reason="r1",
            required_target_capabilities={AgentCapabilityTag.REVIEW},
        )
    )
    registry.add_handoff_route(
        HandoffRoute(
            source_role="router",
            target_role="worker",
            reason="w1",
            required_target_capabilities={AgentCapabilityTag.BACKGROUND_EXECUTION},
        )
    )
    registry.set_handoff_fallback_policy(
        HandoffFallbackPolicy(
            source_role="router",
            target_role="reviewer",
            fallback_target_roles=["ghost_role", "worker"],
        )
    )
    registry.unregister("agent_reviewer")
    resolved = registry.resolve_handoff_target("agent_router", target_role="reviewer")
    assert resolved is not None
    assert resolved.agent_id == "agent_worker"


def test_resolve_handoff_fallback_skips_candidate_missing_required_capability() -> None:
    registry = AgentRegistry()
    registry.register(
        AgentSpec(agent_id="a_router", role="router", capability_tags={AgentCapabilityTag.TOOL_USE})
    )
    registry.register(
        AgentSpec(agent_id="a_target", role="target", capability_tags={AgentCapabilityTag.TOOL_USE})
    )
    registry.register(
        AgentSpec(
            agent_id="a_fb",
            role="fallback",
            capability_tags={AgentCapabilityTag.TOOL_USE},
        )
    )
    registry.add_handoff_route(
        HandoffRoute(
            source_role="router",
            target_role="target",
            reason="x",
            required_target_capabilities={AgentCapabilityTag.TOOL_USE},
        )
    )
    registry.add_handoff_route(
        HandoffRoute(
            source_role="router",
            target_role="fallback",
            reason="x",
            required_target_capabilities={AgentCapabilityTag.TOOL_USE},
        )
    )
    registry.set_handoff_fallback_policy(
        HandoffFallbackPolicy(
            source_role="router",
            target_role="target",
            fallback_target_roles=["fallback"],
        )
    )
    registry.unregister("a_target")
    resolved = registry.resolve_handoff_target(
        "a_router",
        target_role="target",
        required_capability=AgentCapabilityTag.REVIEW,
    )
    assert resolved is None


def test_resolve_handoff_explicit_target_returns_primary_when_eligible() -> None:
    registry = _build_registry()
    registry.add_handoff_route(
        HandoffRoute(
            source_role="router",
            target_role="reviewer",
            reason="r1",
            required_target_capabilities={AgentCapabilityTag.REVIEW},
        )
    )
    resolved = registry.resolve_handoff_target(
        "agent_router",
        target_role="reviewer",
        required_capability=AgentCapabilityTag.REVIEW,
    )
    assert resolved is not None
    assert resolved.agent_id == "agent_reviewer"


def test_resolve_handoff_fallback_duplicate_roles_only_considered_once() -> None:
    registry = _build_registry()
    registry.add_handoff_route(
        HandoffRoute(
            source_role="router",
            target_role="reviewer",
            reason="r1",
            required_target_capabilities={AgentCapabilityTag.REVIEW},
        )
    )
    registry.add_handoff_route(
        HandoffRoute(
            source_role="router",
            target_role="worker",
            reason="w1",
            required_target_capabilities={AgentCapabilityTag.BACKGROUND_EXECUTION},
        )
    )
    registry.set_handoff_fallback_policy(
        HandoffFallbackPolicy(
            source_role="router",
            target_role="reviewer",
            fallback_target_roles=["worker", "worker"],
        )
    )
    registry.unregister("agent_reviewer")
    resolved = registry.resolve_handoff_target("agent_router", target_role="reviewer")
    assert resolved is not None
    assert resolved.agent_id == "agent_worker"


def test_resolve_handoff_returns_none_when_no_route_to_explicit_target() -> None:
    registry = AgentRegistry()
    registry.register(
        AgentSpec(agent_id="a1", role="r1", capability_tags={AgentCapabilityTag.TOOL_USE})
    )
    registry.register(
        AgentSpec(agent_id="a2", role="r2", capability_tags={AgentCapabilityTag.TOOL_USE})
    )
    assert registry.resolve_handoff_target("a1", target_role="r2") is None


def test_resolve_handoff_skips_duplicate_fallback_role_in_runtime_list() -> None:
    """Exercise seen_roles guard when fallback list contains repeated roles (defensive)."""
    registry = _build_registry()
    registry.add_handoff_route(
        HandoffRoute(
            source_role="router",
            target_role="reviewer",
            reason="r1",
            required_target_capabilities={AgentCapabilityTag.REVIEW},
        )
    )
    registry.add_handoff_route(
        HandoffRoute(
            source_role="router",
            target_role="worker",
            reason="w1",
            required_target_capabilities={AgentCapabilityTag.BACKGROUND_EXECUTION},
        )
    )
    registry.set_handoff_fallback_policy(
        HandoffFallbackPolicy(
            source_role="router",
            target_role="reviewer",
            fallback_target_roles=["worker"],
        )
    )
    registry.unregister("agent_reviewer")
    key = ("router", "reviewer")
    registry._fallback_roles[key] = ["worker", "worker"]
    resolved = registry.resolve_handoff_target("agent_router", target_role="reviewer")
    assert resolved is not None
    assert resolved.agent_id == "agent_worker"
