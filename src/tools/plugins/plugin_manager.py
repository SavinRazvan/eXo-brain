"""
File: plugin_manager.py
Path: src/tools/plugins/plugin_manager.py
Role: Plugin lifecycle manager for load/unload/reload with compatibility checks.
Used By:
 - src/tools/executor.py
Depends On:
 - src/tools/registry.py
 - src/tools/plugins/plugin_contract.py
Notes:
 - Unload blocks when active non-idempotent work is reported.
"""

from __future__ import annotations

from src.tools.plugins.plugin_contract import ToolPlugin
from src.tools.registry import ToolRegistry


class PluginManager:
    def __init__(self, registry: ToolRegistry, core_major_version: int = 1) -> None:
        self._registry = registry
        self._core_major_version = core_major_version
        self._plugins: dict[str, ToolPlugin] = {}
        self._plugin_tool_names: dict[str, list[str]] = {}

    def load_plugin(self, plugin: ToolPlugin) -> None:
        self.validate_compatibility(plugin)
        plugin_id = plugin.manifest.plugin_id
        if plugin_id in self._plugins:
            raise ValueError(f"Plugin '{plugin_id}' is already loaded")
        for descriptor in plugin.tools:
            self._registry.register(descriptor)
        self._plugins[plugin_id] = plugin
        self._plugin_tool_names[plugin_id] = [tool.name for tool in plugin.tools]

    def unload_plugin(self, plugin_id: str, has_active_non_idempotent_tasks: bool = False) -> None:
        if has_active_non_idempotent_tasks:
            raise RuntimeError("Cannot unload plugin while active non-idempotent tasks exist")
        if plugin_id not in self._plugins:
            raise KeyError(f"Plugin '{plugin_id}' is not loaded")
        # Registry currently has no explicit unregister API; keep loaded tools immutable once registered.
        del self._plugins[plugin_id]
        del self._plugin_tool_names[plugin_id]

    def reload_plugin(self, plugin: ToolPlugin, has_active_non_idempotent_tasks: bool = False) -> None:
        plugin_id = plugin.manifest.plugin_id
        if plugin_id in self._plugins:
            self.unload_plugin(plugin_id, has_active_non_idempotent_tasks=has_active_non_idempotent_tasks)
        self.load_plugin(plugin)

    def validate_compatibility(self, plugin: ToolPlugin) -> None:
        if plugin.manifest.compatible_core_major != self._core_major_version:
            raise ValueError(
                f"Plugin '{plugin.manifest.plugin_id}' requires core major "
                f"{plugin.manifest.compatible_core_major}, expected {self._core_major_version}"
            )

    def list_plugins(self) -> list[str]:
        return sorted(self._plugins.keys())
