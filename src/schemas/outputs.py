"""
File: outputs.py
Path: src/schemas/outputs.py
Role: Typed output envelopes for streamed deltas and finalized run outputs.
Used By:
 - src/core/orchestrator.py
 - src/integration/host_adapter.py
Depends On:
 - dataclasses
Notes:
 - Keep output contracts provider-neutral and stable for host integrations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class OutputStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(slots=True)
class OutputDelta:
    session_id: str
    run_id: str
    correlation_id: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class FinalOutput:
    session_id: str
    run_id: str
    correlation_id: str
    status: OutputStatus
    output: dict[str, Any] = field(default_factory=dict)
    errors: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_success(self) -> bool:
        return self.status == OutputStatus.COMPLETED and not self.errors
