"""
File: plugin_contract.py
Path: src/agents/plugin_contract.py
Role: Plugin lifecycle contracts for agent modules and routing policies.
Used By:
 - src/agents/plugin_manager.py
 - tests/unit/test_agent_plugins.py
Depends On:
 - dataclasses
 - src/agents/contracts.py
Notes:
 - Keeps agent extension lifecycle outside orchestration core.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.agents.contracts import AgentSpec, HandoffFallbackPolicy, HandoffRoute


@dataclass(slots=True)
class AgentPluginManifest:
    plugin_id: str
    version: str
    compatible_core_major: int
    display_name: str = ""
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class AgentPlugin:
    manifest: AgentPluginManifest
    agents: list[AgentSpec] = field(default_factory=list)
    routes: list[HandoffRoute] = field(default_factory=list)
    fallback_policies: list[HandoffFallbackPolicy] = field(default_factory=list)
