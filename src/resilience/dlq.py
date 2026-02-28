"""
File: dlq.py
Path: src/resilience/dlq.py
Role: Dead-letter queue sink for exhausted execution failures.
Used By:
 - src/mcp/mcp_tool_adapter.py
Depends On:
 - dataclasses
Notes:
 - Captures failure context for audit/replay triage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class DlqRecord:
    correlation_id: str
    reason_code: str
    payload: dict[str, Any] = field(default_factory=dict)


class DeadLetterQueue:
    def __init__(self) -> None:
        self._records: list[DlqRecord] = []

    def push(self, record: DlqRecord) -> None:
        self._records.append(record)

    def list_records(self) -> list[DlqRecord]:
        return list(self._records)

