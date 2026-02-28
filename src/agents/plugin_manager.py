"""
File: plugin_manager.py
Path: src/agents/plugin_manager.py
Role: Agent plugin lifecycle manager for load/unload/reload with compatibility checks.
Used By:
 - tests/unit/test_agent_plugins.py
Depends On:
 - src/agents/registry.py
 - src/agents/plugin_contract.py
Notes:
 - Unload blocks when active non-idempotent tasks are in-flight.
"""

from __future__ import annotations

from src.agents.plugin_contract import AgentPlugin
from src.agents.registry import AgentRegistry


class AgentPluginManager:
    def __init__(self, registry: AgentRegistry, core_major_version: int = 1) -> None:
        self._registry = registry
        self._core_major_version = core_major_version
        self._plugins: dict[str, AgentPlugin] = {}
        self._plugin_agent_ids: dict[str, list[str]] = {}

    def load_plugin(self, plugin: AgentPlugin) -> None:
        self.validate_compatibility(plugin)
        plugin_id = plugin.manifest.plugin_id
        if plugin_id in self._plugins:
            raise ValueError(f"Plugin '{plugin_id}' is already loaded")

        registered_ids: list[str] = []
        try:
            for agent in plugin.agents:
                self._registry.register(agent)
                registered_ids.append(agent.agent_id)
            for route in plugin.routes:
                self._registry.add_handoff_route(route)
            for policy in plugin.fallback_policies:
                self._registry.set_handoff_fallback_policy(policy)
        except Exception:
            for agent_id in reversed(registered_ids):
                self._registry.unregister(agent_id)
            raise

        self._plugins[plugin_id] = plugin
        self._plugin_agent_ids[plugin_id] = registered_ids

    def unload_plugin(self, plugin_id: str, has_active_non_idempotent_tasks: bool = False) -> None:
        if has_active_non_idempotent_tasks:
            raise RuntimeError("Cannot unload plugin while active non-idempotent tasks exist")
        if plugin_id not in self._plugins:
            raise KeyError(f"Plugin '{plugin_id}' is not loaded")

        for agent_id in reversed(self._plugin_agent_ids[plugin_id]):
            self._registry.unregister(agent_id)
        del self._plugins[plugin_id]
        del self._plugin_agent_ids[plugin_id]

    def reload_plugin(self, plugin: AgentPlugin, has_active_non_idempotent_tasks: bool = False) -> None:
        plugin_id = plugin.manifest.plugin_id
        if plugin_id in self._plugins:
            self.unload_plugin(plugin_id, has_active_non_idempotent_tasks=has_active_non_idempotent_tasks)
        self.load_plugin(plugin)

    def validate_compatibility(self, plugin: AgentPlugin) -> None:
        if plugin.manifest.compatible_core_major != self._core_major_version:
            raise ValueError(
                f"Plugin '{plugin.manifest.plugin_id}' requires core major "
                f"{plugin.manifest.compatible_core_major}, expected {self._core_major_version}"
            )

    def list_plugins(self) -> list[str]:
        return sorted(self._plugins.keys())
