"""
File: middleware.py
Path: src/policies/middleware.py
Role: Policy middleware contracts and default deterministic-first implementation.
Used By:
 - src/runtime/mode_selector.py
 - src/tools/executor.py
 - src/core/orchestrator.py
Depends On:
 - src/schemas/tool_io.py
Notes:
 - Policy decisions are auditable and must include reason codes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from src.policies.risk_gates import RiskGateConfig, RiskGatePolicy
from src.schemas.tool_io import (
    PolicyDecision,
    ToolCallContext,
    ToolResult,
)


class PolicyMiddleware(ABC):
    @abstractmethod
    def before_tool_call(self, context: ToolCallContext) -> PolicyDecision:
        raise NotImplementedError

    @abstractmethod
    def after_tool_call(self, result: ToolResult) -> ToolResult:
        raise NotImplementedError

    @abstractmethod
    def before_output(self, output: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError


class DeterministicFirstPolicyMiddleware(PolicyMiddleware):
    def __init__(
        self,
        policy_id: str = "policy-risk-gate-v1",
        policy_version: str = "1.0.0",
        risk_gate_config: RiskGateConfig | None = None,
    ) -> None:
        self._policy_id = policy_id
        self._policy_version = policy_version
        self._risk_gates = RiskGatePolicy(config=risk_gate_config)

    def before_tool_call(self, context: ToolCallContext) -> PolicyDecision:
        return self._risk_gates.evaluate(
            context=context,
            policy_id=self._policy_id,
            policy_version=self._policy_version,
        )

    def after_tool_call(self, result: ToolResult) -> ToolResult:
        return result

    def before_output(self, output: dict[str, Any]) -> dict[str, Any]:
        return output

