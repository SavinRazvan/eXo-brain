"""
File: plugin_contract.py
Path: src/agents/plugin_contract.py
Role: Dataclasses for **agent** plugins: manifests, registered `AgentSpec` entries, handoff routes, and fallback policies (orchestration-facing agent extension surface).
Used By:
 - src/agents/plugin_manager.py
 - tests/modules/agents/test_agent_plugins.py
Depends On:
 - dataclasses
 - src/agents/contracts.py
Notes:
 - Not the user/tool plugin contract — see `src/tools/plugins/plugin_contract.py` (`ToolPlugin`, `ToolDescriptor`).
 - Keeps agent extension lifecycle outside orchestration core.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.agents.contracts import AgentSpec, HandoffFallbackPolicy, HandoffRoute


@dataclass(slots=True)
class AgentPluginManifest:
    """Identity and compatibility metadata for a packaged agent plugin."""
    plugin_id: str
    version: str
    compatible_core_major: int
    display_name: str = ""
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class AgentPlugin:
    """Loaded agent plugin: manifest plus agent specs and optional handoff routing."""
    manifest: AgentPluginManifest
    agents: list[AgentSpec] = field(default_factory=list)
    routes: list[HandoffRoute] = field(default_factory=list)
    fallback_policies: list[HandoffFallbackPolicy] = field(default_factory=list)
