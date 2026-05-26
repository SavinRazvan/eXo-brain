"""
File: tool_io.py
Path: packages/exo-brain-core-contracts/src/exo_brain_core_contracts/tool_io.py
Role: Versioned tool-call and result contracts shared across planes.
Used By:
 - packages/exo-brain-core-contracts/src/exo_brain_core_contracts/runtime_adapter.py
 - packages/exo-brain-core-contracts/src/exo_brain_core_contracts/events.py
 - src/schemas/tool_io.py (control-plane re-export)
Depends On:
 - dataclasses
 - enum
Notes:
 - Keep append-only compatibility for downstream adapters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RiskTier(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ToolExecutionMode(str, Enum):
    PROVIDER_NATIVE = "provider_native"
    DETERMINISTIC = "deterministic"
    AUTO = "auto"


class PolicyAction(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    ESCALATE = "escalate"


class ToolStatus(str, Enum):
    SUCCESS = "success"
    ERROR = "error"
    BLOCKED = "blocked"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass(slots=True)
class NormalizedError:
    code: str | None = None
    category: str | None = None
    message: str | None = None
    retryable: bool = False
    details: dict[str, Any] | None = None


@dataclass(slots=True)
class ToolCallContext:
    schema_version: str
    call_id: str
    session_id: str
    run_id: str
    job_id: str
    task_id: str
    agent_id: str
    provider_id: str
    tool_name: str
    arguments: dict[str, Any]
    tenant_id: str = "default"
    identity_tenant_id: str = ""
    identity_subject: str = ""
    identity_roles: list[str] = field(default_factory=list)
    plugin_scope: str = ""
    risk_tier: RiskTier = RiskTier.LOW
    is_state_changing: bool = False
    requested_mode: ToolExecutionMode = ToolExecutionMode.AUTO
    timestamp_utc: str = ""


@dataclass(slots=True)
class PolicyAudit:
    policy_id: str
    policy_version: str
    correlation_id: str


@dataclass(slots=True)
class PolicyDecision:
    schema_version: str
    decision: PolicyAction
    reason_code: str
    message: str
    enforced_mode: ToolExecutionMode | None = None
    review_required: bool = False
    review_channel: str | None = None
    audit: PolicyAudit | None = None


@dataclass(slots=True)
class ExecutionMetadata:
    mode_used: ToolExecutionMode
    started_at_utc: str = ""
    finished_at_utc: str = ""
    duration_ms: int = 0
    attempt: int = 1
    timeout_ms: int = 30000


@dataclass(slots=True)
class ToolAudit:
    correlation_id: str
    decision_reason_code: str | None = None


@dataclass(slots=True)
class ToolResult:
    schema_version: str
    call_id: str
    tool_name: str
    status: ToolStatus
    result: dict[str, Any] | None = None
    error: NormalizedError = field(default_factory=NormalizedError)
    execution: ExecutionMetadata = field(
        default_factory=lambda: ExecutionMetadata(mode_used=ToolExecutionMode.DETERMINISTIC)
    )
    audit: ToolAudit | None = None


def blocked_result(context: ToolCallContext, reason_code: str, message: str) -> ToolResult:
    return ToolResult(
        schema_version="1.0",
        call_id=context.call_id,
        tool_name=context.tool_name,
        status=ToolStatus.BLOCKED,
        error=NormalizedError(
            code="POLICY_BLOCKED",
            category="policy",
            message=message,
            retryable=False,
            details={"reason_code": reason_code},
        ),
        execution=ExecutionMetadata(mode_used=ToolExecutionMode.DETERMINISTIC),
        audit=ToolAudit(correlation_id=context.call_id, decision_reason_code=reason_code),
    )
