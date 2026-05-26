"""
File: events.py
Path: packages/exo-brain-core-contracts/src/exo_brain_core_contracts/events.py
Role: Provider-neutral runtime event envelopes for streaming and orchestration.
Used By:
 - packages/exo-brain-core-contracts/src/exo_brain_core_contracts/runtime_adapter.py
 - src/schemas/events.py (control-plane re-export)
Depends On:
 - dataclasses
 - enum
 - packages/exo-brain-core-contracts/src/exo_brain_core_contracts/tool_io.py
Notes:
 - Keep payloads generic to avoid provider leakage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from exo_brain_core_contracts.tool_io import ToolCallContext


class RuntimeEventType(str, Enum):
    TOOL_INTENT = "tool_intent"
    TOOL_PROGRESS = "tool_progress"
    OUTPUT_DELTA = "output_delta"
    RUN_COMPLETE = "run_complete"
    ERROR = "error"


@dataclass(slots=True)
class RuntimeEvent:
    event_type: RuntimeEventType
    session_id: str
    run_id: str
    correlation_id: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    tool_call: ToolCallContext | None = None

    @classmethod
    def tool_intent(
        cls,
        session_id: str,
        run_id: str,
        call: ToolCallContext,
        correlation_id: str = "",
    ) -> "RuntimeEvent":
        return cls(
            event_type=RuntimeEventType.TOOL_INTENT,
            session_id=session_id,
            run_id=run_id,
            correlation_id=correlation_id or run_id,
            tool_call=call,
        )

    @classmethod
    def output_delta(
        cls,
        session_id: str,
        run_id: str,
        text: str,
        correlation_id: str = "",
    ) -> "RuntimeEvent":
        return cls(
            event_type=RuntimeEventType.OUTPUT_DELTA,
            session_id=session_id,
            run_id=run_id,
            correlation_id=correlation_id or run_id,
            payload={"text": text},
        )

    @classmethod
    def tool_progress(
        cls,
        session_id: str,
        run_id: str,
        *,
        call_id: str,
        tool_name: str,
        state: str,
        tool_status: str = "",
        error_code: str = "",
        job_id: str = "",
        lease_token: str = "",
        lease_expires_at_epoch: str = "",
        claim_attempt: str = "",
        correlation_id: str = "",
    ) -> "RuntimeEvent":
        return cls(
            event_type=RuntimeEventType.TOOL_PROGRESS,
            session_id=session_id,
            run_id=run_id,
            correlation_id=correlation_id or run_id,
            payload={
                "call_id": call_id,
                "tool_name": tool_name,
                "state": state,
                "tool_status": tool_status,
                "error_code": error_code,
                "job_id": job_id,
                "lease_token": lease_token,
                "lease_expires_at_epoch": lease_expires_at_epoch,
                "claim_attempt": claim_attempt,
            },
        )

    @classmethod
    def run_complete(
        cls,
        session_id: str,
        run_id: str,
        output: dict[str, Any] | None = None,
        correlation_id: str = "",
    ) -> "RuntimeEvent":
        return cls(
            event_type=RuntimeEventType.RUN_COMPLETE,
            session_id=session_id,
            run_id=run_id,
            correlation_id=correlation_id or run_id,
            payload=output or {},
        )

    @classmethod
    def error(
        cls,
        session_id: str,
        run_id: str,
        code: str,
        message: str,
        correlation_id: str = "",
    ) -> "RuntimeEvent":
        return cls(
            event_type=RuntimeEventType.ERROR,
            session_id=session_id,
            run_id=run_id,
            correlation_id=correlation_id or run_id,
            payload={"code": code, "message": message},
        )
