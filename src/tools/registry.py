"""
File: registry.py
Path: src/tools/registry.py
Role: Descriptor-driven tool registry for deterministic tool runtime.
Used By:
 - src/tools/executor.py
 - src/core/orchestrator.py
Depends On:
 - dataclasses
 - src/schemas/tool_io.py
Notes:
 - Registry remains provider-neutral and plugin-friendly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from src.schemas.tool_io import RiskTier

ToolCallable = Callable[..., Any]


@dataclass(slots=True)
class ToolDescriptor:
    name: str
    handler: ToolCallable
    risk_tier: RiskTier = RiskTier.LOW
    is_state_changing: bool = False
    timeout_ms: int = 30000
    metadata: dict[str, Any] = field(default_factory=dict)


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDescriptor] = {}

    def register(self, descriptor: ToolDescriptor) -> None:
        self._tools[descriptor.name] = descriptor

    def resolve(self, tool_name: str) -> ToolDescriptor:
        descriptor = self._tools.get(tool_name)
        if descriptor is None:
            raise KeyError(f"Tool '{tool_name}' not found")
        return descriptor

    def list_tools(self) -> list[str]:
        return sorted(self._tools.keys())
