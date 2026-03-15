"""
File: execution_adapter.py
Path: packages/exo-brain-adapter-sdk/src/exo_brain_adapter_sdk/execution_adapter.py
Role: Adapter SDK execution contract decoupled from monorepo registry types.
Used By:
 - provider execution backends
Depends On:
 - abc
 - exo_brain_core_contracts tool envelopes
Notes:
 - Uses a protocol-like descriptor shape to avoid hard dependency on core registry implementation.
 - Requires exo-brain-core-contracts as a direct pip dependency (no monorepo fallback).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from exo_brain_core_contracts.tool_io import ToolCallContext, ToolResult


@dataclass(slots=True)
class AdapterToolDescriptor:
    name: str
    handler_ref: str = ""
    timeout_ms: int = 30000
    metadata: dict[str, Any] = field(default_factory=dict)


class ToolExecutionAdapterContract(ABC):
    @property
    @abstractmethod
    def backend_id(self) -> str:
        """Stable backend identifier for observability."""

    @abstractmethod
    def execute(self, call: ToolCallContext, descriptor: AdapterToolDescriptor) -> ToolResult:
        """Execute a tool call and return a normalized result envelope."""
