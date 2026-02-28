"""
File: plugin_contract.py
Path: src/tools/plugins/plugin_contract.py
Role: Plugin lifecycle contracts for tool extension modules.
Used By:
 - src/tools/plugins/plugin_manager.py
Depends On:
 - dataclasses
 - src/tools/registry.py
Notes:
 - Plugin contracts keep extension ownership outside orchestration core.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.tools.registry import ToolDescriptor


@dataclass(slots=True)
class PluginManifest:
    plugin_id: str
    version: str
    compatible_core_major: int
    display_name: str = ""
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class ToolPlugin:
    manifest: PluginManifest
    tools: list[ToolDescriptor] = field(default_factory=list)
