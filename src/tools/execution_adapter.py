"""
File: execution_adapter.py
Path: src/tools/execution_adapter.py
Role: Define provider-neutral contracts for pluggable tool execution backends.
Used By:
 - src/tools/executor.py
 - src/tools/sandbox/runtime.py
Depends On:
 - abc
 - src/schemas/tool_io.py
 - src/tools/registry.py
Notes:
 - This contract is synchronous to match the current deterministic executor path.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.schemas.tool_io import ToolCallContext, ToolResult
from src.tools.registry import ToolDescriptor


class ToolExecutionAdapter(ABC):
    """Contract for execution backends used by the deterministic tool executor."""

    @property
    @abstractmethod
    def backend_id(self) -> str:
        """Stable backend identifier for observability and diagnostics."""

    @abstractmethod
    def execute(self, call: ToolCallContext, descriptor: ToolDescriptor) -> ToolResult:
        """Execute the tool call and return a normalized result envelope."""

    def request_cancellation(self, call_id: str) -> bool:
        """Best-effort cancellation hook for adapters that support cancellation tokens."""
        _ = call_id
        return False

    def control_stats(self) -> dict[str, int]:
        """Optional runtime control counters for observability."""
        return {}

    def cleanup_events(self, limit: int = 20) -> list[dict[str, str]]:
        """Optional recent cleanup events for runtime worker lifecycle diagnostics."""
        _ = limit
        return []

    def drain_progress_events(self, call_id: str) -> list[dict[str, str]]:
        """Optional tool progress events emitted by the adapter for a call_id."""
        _ = call_id
        return []

    def manages_progress_events(self) -> bool:
        """Return True when the adapter emits its own lifecycle progress events."""
        return False
