"""
File: test_agent_plugins.py
Path: tests/modules/agents/test_agent_plugins.py
Role: Unit tests for agent plugin lifecycle manager and registry integration.
Used By:
 - pytest
Depends On:
 - src/agents/contracts.py
 - src/agents/plugin_contract.py
 - src/agents/plugin_manager.py
 - src/agents/registry.py
Notes:
 - Covers load/unload/reload compatibility and fallback policy registration.
"""

from __future__ import annotations

import pytest

from src.agents.contracts import AgentCapabilityTag, AgentSpec, HandoffFallbackPolicy, HandoffRoute
from src.agents.plugin_contract import AgentPlugin, AgentPluginManifest
from src.agents.plugin_manager import AgentPluginManager, LifecyclePolicyDecision
from src.agents.registry import AgentRegistry
from src.schemas.tool_io import PolicyAction


def _base_registry() -> AgentRegistry:
    registry = AgentRegistry()
    registry.register(
        AgentSpec(
            agent_id="agent_router",
            role="router",
            capability_tags={AgentCapabilityTag.WORKFLOW_ROUTING},
        )
    )
    return registry


def _review_plugin() -> AgentPlugin:
    return AgentPlugin(
        manifest=AgentPluginManifest(
            plugin_id="review-pack",
            version="1.0.0",
            compatible_core_major=1,
        ),
        agents=[
            AgentSpec(
                agent_id="agent_reviewer",
                role="reviewer",
                capability_tags={AgentCapabilityTag.REVIEW, AgentCapabilityTag.TOOL_USE},
            ),
            AgentSpec(
                agent_id="agent_backup",
                role="backup_reviewer",
                capability_tags={AgentCapabilityTag.REVIEW, AgentCapabilityTag.TOOL_USE},
            ),
        ],
        routes=[
            HandoffRoute(
                source_role="router",
                target_role="reviewer",
                reason="review-stage",
                required_target_capabilities={AgentCapabilityTag.REVIEW},
            ),
            HandoffRoute(
                source_role="router",
                target_role="backup_reviewer",
                reason="fallback-review-stage",
                required_target_capabilities={AgentCapabilityTag.REVIEW},
            ),
        ],
        fallback_policies=[
            HandoffFallbackPolicy(
                source_role="router",
                target_role="reviewer",
                fallback_target_roles=["backup_reviewer"],
                target_role_priorities={"backup_reviewer": 100},
            )
        ],
    )


class _DenyUnloadLifecyclePolicy:
    def evaluate(
        self,
        *,
        action: str,
        plugin_id: str,
        has_active_non_idempotent_tasks: bool,
    ) -> LifecyclePolicyDecision:
        if action == "unload":
            return LifecyclePolicyDecision(
                decision=PolicyAction.DENY,
                reason_code="AGENT_LIFECYCLE_DENY_UNLOAD",
                message=f"Unload is denied for plugin '{plugin_id}'.",
            )
        return LifecyclePolicyDecision(
            decision=PolicyAction.ALLOW,
            reason_code="AGENT_LIFECYCLE_ALLOW",
            message="Allowed by test policy.",
        )


def test_agent_plugin_manager_loads_agents_routes_and_fallbacks() -> None:
    registry = _base_registry()
    manager = AgentPluginManager(registry=registry, core_major_version=1)

    manager.load_plugin(_review_plugin())

    assert manager.list_plugins() == ["review-pack"]
    resolved = registry.resolve_handoff_target("agent_router", target_role="reviewer")
    assert resolved is not None
    assert resolved.agent_id == "agent_reviewer"


def test_agent_plugin_manager_unload_removes_plugin_agents() -> None:
    registry = _base_registry()
    manager = AgentPluginManager(registry=registry, core_major_version=1)
    manager.load_plugin(_review_plugin())

    manager.unload_plugin("review-pack")

    assert manager.list_plugins() == []
    with pytest.raises(KeyError, match="Unknown agent_id"):
        registry.get("agent_reviewer")


def test_agent_plugin_manager_blocks_incompatible_plugin() -> None:
    registry = _base_registry()
    manager = AgentPluginManager(registry=registry, core_major_version=1)
    incompatible = AgentPlugin(
        manifest=AgentPluginManifest(
            plugin_id="future-pack",
            version="2.0.0",
            compatible_core_major=2,
        ),
    )

    with pytest.raises(ValueError, match="requires core major"):
        manager.load_plugin(incompatible)


def test_agent_plugin_manager_blocks_unload_when_non_idempotent_tasks_active() -> None:
    registry = _base_registry()
    manager = AgentPluginManager(registry=registry, core_major_version=1)
    manager.load_plugin(_review_plugin())

    with pytest.raises(RuntimeError, match="non-idempotent tasks"):
        manager.unload_plugin("review-pack", has_active_non_idempotent_tasks=True)


def test_agent_plugin_manager_rejects_unknown_fallback_priority_role() -> None:
    registry = _base_registry()
    manager = AgentPluginManager(registry=registry, core_major_version=1)
    invalid = AgentPlugin(
        manifest=AgentPluginManifest(
            plugin_id="invalid-priority-pack",
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
                target_role_priorities={"missing-role": 1},
            )
        ],
    )

    with pytest.raises(ValueError, match="unknown target role"):
        manager.load_plugin(invalid)


def test_agent_plugin_manager_blocks_lifecycle_action_when_policy_denies() -> None:
    registry = _base_registry()
    manager = AgentPluginManager(
        registry=registry,
        core_major_version=1,
        lifecycle_policy=_DenyUnloadLifecyclePolicy(),
    )
    manager.load_plugin(_review_plugin())

    with pytest.raises(PermissionError, match="AGENT_LIFECYCLE_DENY_UNLOAD"):
        manager.unload_plugin("review-pack")

    assert manager.list_plugins() == ["review-pack"]
    assert registry.get("agent_reviewer").role == "reviewer"


def test_agent_plugin_manager_reload_restores_previous_plugin_on_failure() -> None:
    registry = _base_registry()
    manager = AgentPluginManager(registry=registry, core_major_version=1)
    manager.load_plugin(_review_plugin())

    incompatible_reload = AgentPlugin(
        manifest=AgentPluginManifest(
            plugin_id="review-pack",
            version="2.0.0",
            compatible_core_major=2,
        )
    )

    with pytest.raises(ValueError, match="requires core major"):
        manager.reload_plugin(incompatible_reload)

    assert manager.list_plugins() == ["review-pack"]
    assert registry.get("agent_reviewer").role == "reviewer"


def test_agent_plugin_manager_emits_lifecycle_audit_records() -> None:
    registry = _base_registry()
    manager = AgentPluginManager(registry=registry, core_major_version=1)
    manager.load_plugin(_review_plugin())

    records = manager.list_lifecycle_audit_records()
    reason_codes = {record.reason_code for record in records}
    actions = {record.action for record in records}

    assert "load" in actions
    assert "AGENT_PLUGIN_LOADED" in reason_codes


def test_plugin_churn_preserves_deterministic_fallback_resolution() -> None:
    registry = _base_registry()
    manager = AgentPluginManager(registry=registry, core_major_version=1)
    plugin = _review_plugin()
    manager.load_plugin(plugin)

    registry.unregister("agent_reviewer")
    first_resolution = registry.resolve_handoff_target("agent_router", target_role="reviewer")
    assert first_resolution is not None
    assert first_resolution.agent_id == "agent_backup"

    manager.reload_plugin(plugin)
    registry.unregister("agent_reviewer")
    second_resolution = registry.resolve_handoff_target("agent_router", target_role="reviewer")
    assert second_resolution is not None
    assert second_resolution.agent_id == "agent_backup"
