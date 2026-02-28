"""
File: test_agent_plugins.py
Path: tests/unit/test_agent_plugins.py
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
from src.agents.plugin_manager import AgentPluginManager
from src.agents.registry import AgentRegistry


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
            )
        ],
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
