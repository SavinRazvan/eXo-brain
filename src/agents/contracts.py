"""
File: contracts.py
Path: src/agents/contracts.py
Role: Provider-neutral contracts for agent registration, capability tags, and handoff routes.
Used By:
 - src/agents/registry.py
 - src/agents/plugin_contract.py
 - tests/unit/test_agent_registry.py
Depends On:
 - dataclasses
 - enum
Notes:
 - Keep contracts stable so routing and orchestration can evolve independently.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AgentCapabilityTag(str, Enum):
    TOOL_USE = "tool_use"
    WORKFLOW_ROUTING = "workflow_routing"
    REVIEW = "review"
    RETRIEVAL = "retrieval"
    MCP = "mcp"
    BACKGROUND_EXECUTION = "background_execution"


@dataclass(slots=True)
class AgentSpec:
    agent_id: str
    role: str
    capability_tags: set[AgentCapabilityTag] = field(default_factory=set)
    metadata: dict[str, Any] = field(default_factory=dict)

    def has_capability(self, capability: AgentCapabilityTag) -> bool:
        return capability in self.capability_tags


@dataclass(slots=True)
class HandoffRoute:
    source_role: str
    target_role: str
    reason: str
    required_target_capabilities: set[AgentCapabilityTag] = field(default_factory=set)


@dataclass(slots=True)
class HandoffFallbackPolicy:
    source_role: str
    target_role: str
    fallback_target_roles: list[str] = field(default_factory=list)
    target_role_priorities: dict[str, int] = field(default_factory=dict)
