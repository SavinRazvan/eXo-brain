"""
File: tracing.py
Path: src/observability/tracing.py
Role: In-memory tracing primitives for span lifecycle and correlation-aware runtime diagnostics.
Used By:
 - src/core/scheduler.py
 - src/core/background_runtime.py
Depends On:
 - dataclasses
 - datetime
 - uuid
Notes:
 - Tracing is intentionally lightweight and backend-agnostic for local deterministic tests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


@dataclass(slots=True)
class TraceSpan:
    span_id: str
    correlation_id: str
    name: str
    parent_span_id: str | None = None
    status: str = "running"
    started_at_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    finished_at_utc: str = ""
    attributes: dict[str, Any] = field(default_factory=dict)
    error: str = ""


class RuntimeTracer:
    def __init__(self) -> None:
        self._spans: list[TraceSpan] = []
        self._active_by_id: dict[str, TraceSpan] = {}

    def start_span(
        self,
        correlation_id: str,
        name: str,
        parent_span_id: str | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> str:
        span = TraceSpan(
            span_id=f"span_{uuid4().hex}",
            correlation_id=correlation_id,
            name=name,
            parent_span_id=parent_span_id,
            attributes=dict(attributes or {}),
        )
        self._spans.append(span)
        self._active_by_id[span.span_id] = span
        return span.span_id

    def finish_span(
        self,
        span_id: str,
        status: str = "ok",
        attributes: dict[str, Any] | None = None,
        error: str = "",
    ) -> None:
        span = self._active_by_id.get(span_id)
        if span is None:
            return
        if attributes:
            span.attributes.update(attributes)
        span.status = status
        span.error = error
        span.finished_at_utc = datetime.now(timezone.utc).isoformat()
        self._active_by_id.pop(span_id, None)

    def spans_for(self, correlation_id: str) -> list[TraceSpan]:
        return [span for span in self._spans if span.correlation_id == correlation_id]

    def all_spans(self) -> list[TraceSpan]:
        return list(self._spans)
