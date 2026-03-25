"""
File: plugin_contract.py
Path: src/tools/plugins/plugin_contract.py
Role: Dataclasses for **user/tool** plugins: manifests and `ToolDescriptor` registrations (deterministic tool execution surface).
Used By:
 - src/tools/plugins/plugin_manager.py
Depends On:
 - dataclasses
 - src/tools/registry.py
Notes:
 - Not the agent/handoff plugin contract — see `src/agents/plugin_contract.py` (`AgentPlugin`, `HandoffRoute`).
 - Keeps tool extension ownership outside orchestration core.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.tools.registry import ToolDescriptor


@dataclass(slots=True)
class PluginManifest:
    """Identity and compatibility metadata for a packaged tool plugin."""
    plugin_id: str
    version: str
    compatible_core_major: int
    display_name: str = ""
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class ToolPlugin:
    """Loaded tool plugin: manifest plus tool descriptors for the registry."""
    manifest: PluginManifest
    tools: list[ToolDescriptor] = field(default_factory=list)
