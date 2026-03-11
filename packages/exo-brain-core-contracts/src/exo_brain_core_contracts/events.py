"""
File: events.py
Path: packages/exo-brain-core-contracts/src/exo_brain_core_contracts/events.py
Role: Provider-neutral runtime event envelopes for streaming and orchestration.
Used By:
 - packages/exo-brain-core-contracts/src/exo_brain_core_contracts/runtime_adapter.py
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
