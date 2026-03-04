"""
File: policy.py
Path: src/tools/sandbox/policy.py
Role: Centralized hosted sandbox runtime policy for timeout and tenant resolution.
Used By:
 - src/tools/sandbox/runtime.py
Depends On:
 - dataclasses
 - src/schemas/tool_io.py
 - src/tools/registry.py
Notes:
 - This policy is intentionally lightweight and deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.schemas.tool_io import ToolCallContext
from src.tools.registry import ToolDescriptor


@dataclass(slots=True)
class SandboxRuntimePolicy:
    """Platform policy values applied by the hosted runtime."""

    min_timeout_ms: int = 100
    max_timeout_ms: int = 300000

    def resolve_tenant_id(self, call: ToolCallContext) -> str:
        tenant_id = str(call.tenant_id).strip()
        return tenant_id if tenant_id else "default"

    def resolve_timeout_ms(self, descriptor: ToolDescriptor) -> int:
        raw_timeout = descriptor.metadata.get("sandbox_timeout_ms", descriptor.timeout_ms)
        try:
            parsed = int(raw_timeout)
        except (TypeError, ValueError):
            parsed = descriptor.timeout_ms
        return max(self.min_timeout_ms, min(parsed, self.max_timeout_ms))
