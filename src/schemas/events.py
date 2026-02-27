"""
File: events.py
Path: src/schemas/events.py
Role: Runtime event contracts shared across adapters and orchestration.
Used By:
 - src/runtime/runtime_adapter.py
 - src/runtime/openai_agents_runtime.py
 - src/core/orchestrator.py
Depends On:
 - dataclasses
 - enum
 - src/schemas/tool_io.py
Notes:
 - Event envelopes are provider-neutral and intentionally minimal.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from src.schemas.tool_io import ToolCallContext


class RuntimeEventType(str, Enum):
    TOOL_INTENT = "tool_intent"
    OUTPUT_DELTA = "output_delta"
    RUN_COMPLETE = "run_complete"
    ERROR = "error"


@dataclass(slots=True)
class RuntimeEvent:
    event_type: RuntimeEventType
    session_id: str
    run_id: str
    payload: dict[str, Any] = field(default_factory=dict)
    tool_call: ToolCallContext | None = None

    @classmethod
    def tool_intent(cls, session_id: str, run_id: str, call: ToolCallContext) -> "RuntimeEvent":
        return cls(
            event_type=RuntimeEventType.TOOL_INTENT,
            session_id=session_id,
            run_id=run_id,
            tool_call=call,
        )

    @classmethod
    def output_delta(cls, session_id: str, run_id: str, text: str) -> "RuntimeEvent":
        return cls(
            event_type=RuntimeEventType.OUTPUT_DELTA,
            session_id=session_id,
            run_id=run_id,
            payload={"text": text},
        )

    @classmethod
    def run_complete(cls, session_id: str, run_id: str, output: dict[str, Any] | None = None) -> "RuntimeEvent":
        return cls(
            event_type=RuntimeEventType.RUN_COMPLETE,
            session_id=session_id,
            run_id=run_id,
            payload=output or {},
        )

    @classmethod
    def error(cls, session_id: str, run_id: str, code: str, message: str) -> "RuntimeEvent":
        return cls(
            event_type=RuntimeEventType.ERROR,
            session_id=session_id,
            run_id=run_id,
            payload={"code": code, "message": message},
        )
