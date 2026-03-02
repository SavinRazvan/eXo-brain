"""
File: registry.py
Path: src/agents/registry.py
Role: Registry and routing helpers for agent contracts and handoff rules.
Used By:
 - src/agents/plugin_manager.py
 - tests/modules/agents/test_agent_registry.py
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
        self._fallback_role_priorities: dict[tuple[str, str], dict[str, int]] = {}

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
        self._fallback_role_priorities = {
            key: {
                role_name: priority
                for role_name, priority in priority_map.items()
                if role_name != role
            }
            for key, priority_map in self._fallback_role_priorities.items()
            if role != key[0]
        }

    def list_agents(self) -> list[AgentSpec]:
        return [self._agents[agent_id] for agent_id in sorted(self._agents.keys())]

    def list_routes(self) -> list[HandoffRoute]:
        return list(self._routes.values())

    def list_fallback_policies(self) -> list[HandoffFallbackPolicy]:
        policies: list[HandoffFallbackPolicy] = []
        for (source_role, target_role), fallback_roles in self._fallback_roles.items():
            priorities = self._fallback_role_priorities.get((source_role, target_role), {})
            policies.append(
                HandoffFallbackPolicy(
                    source_role=source_role,
                    target_role=target_role,
                    fallback_target_roles=list(fallback_roles),
                    target_role_priorities=dict(priorities),
                )
            )
        return policies

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
        normalized_priorities: dict[str, int] = {}
        for role, priority in policy.target_role_priorities.items():
            role_name = role.strip()
            if not role_name:
                continue
            if role_name not in self._roles:
                raise ValueError(f"Cannot configure priority for unknown target role '{role_name}'")
            normalized_priorities[role_name] = int(priority)
        self._fallback_role_priorities[(policy.source_role, policy.target_role)] = normalized_priorities

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

        primary_target = self._agent_for_role(target_role)
        if primary_target is not None and self._is_candidate_eligible(
            source_agent_id=source_agent_id,
            target=primary_target,
            required_capability=required_capability,
        ):
            return primary_target

        fallback_roles = self._fallback_roles.get((source.role, target_role), [])
        priorities = self._fallback_role_priorities.get((source.role, target_role), {})
        fallback_candidates: list[AgentSpec] = []
        seen_roles: set[str] = {target_role}
        for role in fallback_roles:
            if role in seen_roles:
                continue
            seen_roles.add(role)
            target = self._agent_for_role(role)
            if target is None:
                continue
            if not self._is_candidate_eligible(
                source_agent_id=source_agent_id,
                target=target,
                required_capability=required_capability,
            ):
                continue
            fallback_candidates.append(target)

        fallback_candidates.sort(
            key=lambda agent: (-priorities.get(agent.role, 0), agent.agent_id)
        )
        if fallback_candidates:
            return fallback_candidates[0]
        return None

    def _agent_for_role(self, role: str) -> AgentSpec | None:
        agent_id = self._roles.get(role)
        if agent_id is None:
            return None
        return self._agents.get(agent_id)

    def _is_candidate_eligible(
        self,
        source_agent_id: str,
        target: AgentSpec,
        required_capability: AgentCapabilityTag | None,
    ) -> bool:
        if not self.can_handoff(source_agent_id, target.agent_id):
            return False
        if required_capability and required_capability not in target.capability_tags:
            return False
        return True
