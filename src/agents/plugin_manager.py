"""
File: plugin_manager.py
Path: src/agents/plugin_manager.py
Role: Agent plugin lifecycle manager with policy/audit hooks and compatibility checks.
Used By:
 - tests/modules/agents/test_agent_plugins.py
Depends On:
 - src/agents/registry.py
 - src/agents/plugin_contract.py
 - src/schemas/tool_io.py
Notes:
 - Unload blocks when active non-idempotent tasks are in-flight.
 - Reload failures restore the previous plugin to preserve routing stability.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from src.agents.plugin_contract import AgentPlugin
from src.agents.registry import AgentRegistry
from src.schemas.tool_io import PolicyAction


@dataclass(slots=True)
class LifecyclePolicyDecision:
    decision: PolicyAction
    reason_code: str
    message: str = ""


class LifecyclePolicy(Protocol):
    def evaluate(
        self,
        *,
        action: str,
        plugin_id: str,
        has_active_non_idempotent_tasks: bool,
    ) -> LifecyclePolicyDecision:
        ...


class AllowAllLifecyclePolicy:
    def evaluate(
        self,
        *,
        action: str,
        plugin_id: str,
        has_active_non_idempotent_tasks: bool,
    ) -> LifecyclePolicyDecision:
        return LifecyclePolicyDecision(
            decision=PolicyAction.ALLOW,
            reason_code="AGENT_LIFECYCLE_ALLOWED",
            message=f"Lifecycle action '{action}' allowed for plugin '{plugin_id}'.",
        )


@dataclass(slots=True)
class LifecycleAuditRecord:
    action: str
    plugin_id: str
    decision: PolicyAction
    reason_code: str
    detail: str = ""


class AgentPluginManager:
    def __init__(
        self,
        registry: AgentRegistry,
        core_major_version: int = 1,
        lifecycle_policy: LifecyclePolicy | None = None,
    ) -> None:
        self._registry = registry
        self._core_major_version = core_major_version
        self._lifecycle_policy = lifecycle_policy or AllowAllLifecyclePolicy()
        self._plugins: dict[str, AgentPlugin] = {}
        self._plugin_agent_ids: dict[str, list[str]] = {}
        self._lifecycle_audit_records: list[LifecycleAuditRecord] = []

    def load_plugin(self, plugin: AgentPlugin) -> None:
        self.validate_compatibility(plugin)
        plugin_id = plugin.manifest.plugin_id
        self._authorize(
            action="load",
            plugin_id=plugin_id,
            has_active_non_idempotent_tasks=False,
        )
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
        self._record_lifecycle_event(
            action="load",
            plugin_id=plugin_id,
            decision=PolicyAction.ALLOW,
            reason_code="AGENT_PLUGIN_LOADED",
            detail=f"Registered {len(registered_ids)} agents.",
        )

    def unload_plugin(self, plugin_id: str, has_active_non_idempotent_tasks: bool = False) -> None:
        self._authorize(
            action="unload",
            plugin_id=plugin_id,
            has_active_non_idempotent_tasks=has_active_non_idempotent_tasks,
        )
        if has_active_non_idempotent_tasks:
            raise RuntimeError("Cannot unload plugin while active non-idempotent tasks exist")
        if plugin_id not in self._plugins:
            raise KeyError(f"Plugin '{plugin_id}' is not loaded")

        for agent_id in reversed(self._plugin_agent_ids[plugin_id]):
            try:
                self._registry.unregister(agent_id)
            except KeyError:
                # Agent may have been removed by independent churn before unload/reload.
                continue
        del self._plugins[plugin_id]
        del self._plugin_agent_ids[plugin_id]
        self._record_lifecycle_event(
            action="unload",
            plugin_id=plugin_id,
            decision=PolicyAction.ALLOW,
            reason_code="AGENT_PLUGIN_UNLOADED",
            detail="Plugin agents and routes removed from registry.",
        )

    def reload_plugin(self, plugin: AgentPlugin, has_active_non_idempotent_tasks: bool = False) -> None:
        plugin_id = plugin.manifest.plugin_id
        self._authorize(
            action="reload",
            plugin_id=plugin_id,
            has_active_non_idempotent_tasks=has_active_non_idempotent_tasks,
        )
        previous_plugin = self._plugins.get(plugin_id)
        if plugin_id in self._plugins:
            self.unload_plugin(plugin_id, has_active_non_idempotent_tasks=has_active_non_idempotent_tasks)
        try:
            self.load_plugin(plugin)
        except Exception:
            if previous_plugin is not None:
                self.load_plugin(previous_plugin)
            raise
        self._record_lifecycle_event(
            action="reload",
            plugin_id=plugin_id,
            decision=PolicyAction.ALLOW,
            reason_code="AGENT_PLUGIN_RELOADED",
            detail="Reload completed successfully.",
        )

    def validate_compatibility(self, plugin: AgentPlugin) -> None:
        if plugin.manifest.compatible_core_major != self._core_major_version:
            raise ValueError(
                f"Plugin '{plugin.manifest.plugin_id}' requires core major "
                f"{plugin.manifest.compatible_core_major}, expected {self._core_major_version}"
            )

    def list_plugins(self) -> list[str]:
        return sorted(self._plugins.keys())

    def list_lifecycle_audit_records(self) -> list[LifecycleAuditRecord]:
        return list(self._lifecycle_audit_records)

    def _authorize(
        self,
        *,
        action: str,
        plugin_id: str,
        has_active_non_idempotent_tasks: bool,
    ) -> None:
        decision = self._lifecycle_policy.evaluate(
            action=action,
            plugin_id=plugin_id,
            has_active_non_idempotent_tasks=has_active_non_idempotent_tasks,
        )
        self._record_lifecycle_event(
            action=action,
            plugin_id=plugin_id,
            decision=decision.decision,
            reason_code=decision.reason_code,
            detail=decision.message,
        )
        if decision.decision == PolicyAction.ALLOW:
            return
        raise PermissionError(
            f"Lifecycle action '{action}' blocked for plugin '{plugin_id}': {decision.reason_code}"
        )

    def _record_lifecycle_event(
        self,
        *,
        action: str,
        plugin_id: str,
        decision: PolicyAction,
        reason_code: str,
        detail: str = "",
    ) -> None:
        self._lifecycle_audit_records.append(
            LifecycleAuditRecord(
                action=action,
                plugin_id=plugin_id,
                decision=decision,
                reason_code=reason_code,
                detail=detail,
            )
        )
