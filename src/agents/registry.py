"""
File: registry.py
Path: src/agents/registry.py
Role: Registry and routing helpers for agent contracts and handoff rules.
Used By:
 - src/agents/plugin_manager.py
 - tests/unit/test_agent_registry.py
Depends On:
 - src/agents/contracts.py
Notes:
 - Validates role-based handoff routes, fallback paths, and capability constraints.
"""

from __future__ import annotations

from src.agents.contracts import AgentCapabilityTag, AgentSpec, HandoffFallbackPolicy, HandoffRoute


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, AgentSpec] = {}
        self._roles: dict[str, str] = {}
        self._routes: dict[tuple[str, str], HandoffRoute] = {}
        self._fallback_roles: dict[tuple[str, str], list[str]] = {}

    def register(self, agent: AgentSpec) -> None:
        if not agent.agent_id.strip():
            raise ValueError("agent_id must be a non-empty string")
        if not agent.role.strip():
            raise ValueError("role must be a non-empty string")
        if agent.agent_id in self._agents:
            raise ValueError(f"Agent '{agent.agent_id}' is already registered")
        if agent.role in self._roles:
            raise ValueError(f"Role '{agent.role}' is already bound to another agent")
        self._agents[agent.agent_id] = agent
        self._roles[agent.role] = agent.agent_id

    def get(self, agent_id: str) -> AgentSpec:
        agent = self._agents.get(agent_id)
        if agent is None:
            raise KeyError(f"Unknown agent_id '{agent_id}'")
        return agent

    def get_by_role(self, role: str) -> AgentSpec:
        agent_id = self._roles.get(role)
        if agent_id is None:
            raise KeyError(f"Unknown role '{role}'")
        return self._agents[agent_id]

    def unregister(self, agent_id: str) -> None:
        agent = self.get(agent_id)
        role = agent.role
        del self._agents[agent_id]
        del self._roles[role]

        self._routes = {
            key: route
            for key, route in self._routes.items()
            if role not in key
        }
        self._fallback_roles = {
            key: [fallback_role for fallback_role in fallback_roles if fallback_role != role]
            for key, fallback_roles in self._fallback_roles.items()
            if role != key[0]
        }

    def list_agents(self) -> list[AgentSpec]:
        return [self._agents[agent_id] for agent_id in sorted(self._agents.keys())]

    def find_with_capability(self, capability: AgentCapabilityTag) -> list[AgentSpec]:
        return [
            agent
            for agent in self.list_agents()
            if capability in agent.capability_tags
        ]

    def add_handoff_route(self, route: HandoffRoute) -> None:
        if route.source_role not in self._roles:
            raise ValueError(f"Cannot route from unknown source role '{route.source_role}'")
        if route.target_role not in self._roles:
            raise ValueError(f"Cannot route to unknown target role '{route.target_role}'")

        target = self.get_by_role(route.target_role)
        missing = sorted(
            capability.value
            for capability in route.required_target_capabilities
            if capability not in target.capability_tags
        )
        if missing:
            raise ValueError(
                "Target role does not satisfy required capabilities: "
                + ", ".join(missing)
            )
        self._routes[(route.source_role, route.target_role)] = route

    def set_handoff_fallback_policy(self, policy: HandoffFallbackPolicy) -> None:
        if policy.source_role not in self._roles:
            raise ValueError(f"Cannot configure fallback from unknown source role '{policy.source_role}'")
        if policy.target_role not in self._roles:
            raise ValueError(f"Cannot configure fallback for unknown target role '{policy.target_role}'")

        normalized: list[str] = []
        seen: set[str] = set()
        for role in policy.fallback_target_roles:
            role_name = role.strip()
            if not role_name:
                continue
            if role_name == policy.target_role:
                continue
            if role_name in seen:
                continue
            seen.add(role_name)
            normalized.append(role_name)
        self._fallback_roles[(policy.source_role, policy.target_role)] = normalized

    def can_handoff(self, source_agent_id: str, target_agent_id: str) -> bool:
        source = self.get(source_agent_id)
        target = self.get(target_agent_id)
        route = self._routes.get((source.role, target.role))
        if route is None:
            return False
        return all(
            capability in target.capability_tags
            for capability in route.required_target_capabilities
        )

    def handoff_targets(
        self,
        source_agent_id: str,
        required_capability: AgentCapabilityTag | None = None,
    ) -> list[AgentSpec]:
        source = self.get(source_agent_id)
        targets: list[AgentSpec] = []
        for (source_role, target_role), route in self._routes.items():
            if source_role != source.role:
                continue
            target = self.get_by_role(target_role)
            if required_capability and required_capability not in target.capability_tags:
                continue
            if all(
                capability in target.capability_tags
                for capability in route.required_target_capabilities
            ):
                targets.append(target)
        return sorted(targets, key=lambda agent: agent.agent_id)

    def resolve_handoff_target(
        self,
        source_agent_id: str,
        target_role: str | None = None,
        required_capability: AgentCapabilityTag | None = None,
    ) -> AgentSpec | None:
        source = self.get(source_agent_id)
        if not target_role:
            targets = self.handoff_targets(
                source_agent_id=source_agent_id,
                required_capability=required_capability,
            )
            return targets[0] if targets else None

        candidate_roles = [target_role]
        candidate_roles.extend(self._fallback_roles.get((source.role, target_role), []))
        seen_roles: set[str] = set()
        for role in candidate_roles:
            if role in seen_roles:
                continue
            seen_roles.add(role)
            target_agent_id = self._roles.get(role)
            if target_agent_id is None:
                continue
            target = self._agents[target_agent_id]
            if not self.can_handoff(source_agent_id, target.agent_id):
                continue
            if required_capability and required_capability not in target.capability_tags:
                continue
            return target
        return None
