"""
File: test_observability.py
Path: tests/unit/test_observability.py
Role: Unit tests for observability primitives (logging, metrics, timeline).
Used By:
 - pytest
Depends On:
 - src/observability/logging.py
 - src/observability/metrics.py
 - src/observability/timeline.py
 - src/observability/tracing.py
Notes:
 - Verifies deterministic local observability behavior before backend export wiring.
"""

from __future__ import annotations

from src.observability.logging import LogLevel, StructuredLogger
from src.observability.metrics import RuntimeMetrics
from src.observability.tracing import RuntimeTracer
from src.observability.timeline import RuntimeTimeline


def test_structured_logger_persists_context() -> None:
    logger = StructuredLogger()
    logger.log(
        level=LogLevel.INFO,
        event="runtime.event",
        message="event emitted",
        correlation_id="corr_1",
        context={"job_id": "job_1"},
    )
    records = logger.records()
    assert len(records) == 1
    assert records[0].correlation_id == "corr_1"
    assert records[0].context["job_id"] == "job_1"


def test_runtime_metrics_counter_and_gauge_updates() -> None:
    metrics = RuntimeMetrics()
    metrics.inc("scheduler.node.success")
    metrics.inc("scheduler.node.success")
    metrics.set_gauge("scheduler.queue_depth", 3)
    metrics.observe_latency(12.5)
    assert metrics.counters["scheduler.node.success"] == 2
    assert metrics.gauges["scheduler.queue_depth"] == 3
    assert metrics.latency_ms == [12.5]


def test_runtime_metrics_rate_calculation() -> None:
    metrics = RuntimeMetrics()
    metrics.inc("tool.call.total", 4)
    metrics.inc("tool.call.failed", 1)
    assert metrics.rate("tool.call.failed", "tool.call.total") == 0.25
    assert metrics.rate("tool.call.failed", "tool.call.blocked") == 0.0


def test_runtime_timeline_filters_entries_by_correlation() -> None:
    timeline = RuntimeTimeline()
    timeline.append(correlation_id="job_1", event="job.started")
    timeline.append(correlation_id="job_2", event="job.started")
    timeline.append(correlation_id="job_1", event="job.finished")
    job_entries = timeline.entries_for("job_1")
    assert [entry.event for entry in job_entries] == ["job.started", "job.finished"]


def test_runtime_tracer_records_span_lifecycle() -> None:
    tracer = RuntimeTracer()
    span_id = tracer.start_span(
        correlation_id="job_1",
        name="scheduler.execute",
        attributes={"node_count": 2},
    )
    tracer.finish_span(
        span_id=span_id,
        status="ok",
        attributes={"outcomes": 2},
    )

    spans = tracer.spans_for("job_1")
    assert len(spans) == 1
    assert spans[0].name == "scheduler.execute"
    assert spans[0].status == "ok"
    assert spans[0].attributes["node_count"] == 2
    assert spans[0].attributes["outcomes"] == 2
    assert spans[0].finished_at_utc != ""
