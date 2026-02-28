"""
File: contracts.py
Path: src/access_control/contracts.py
Role: Access-control request and decision contracts for policy evaluation.
Used By:
 - src/access_control/policy_engine.py
 - src/policies/risk_gates.py
Depends On:
 - dataclasses
 - src/schemas/tool_io.py
Notes:
 - Contracts are provider-neutral and operate on internal tool context.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.schemas.tool_io import PolicyAction


@dataclass(slots=True)
class AccessRequest:
    subject: str
    roles: list[str]
    tool_name: str
    is_state_changing: bool
    is_high_impact: bool


@dataclass(slots=True)
class AccessDecision:
    decision: PolicyAction
    reason_code: str
    message: str
    review_required: bool = False
    review_channel: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)

