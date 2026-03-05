"""
File: test_observability.py
Path: tests/modules/observability/test_observability.py
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

import json
from pathlib import Path

from src.observability.logging import FileLogSink, LogLevel, StructuredLogger
from src.observability.metrics import RuntimeMetrics
from src.observability.tracing import FileTraceExporter, RuntimeTracer
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


def test_structured_logger_exports_to_file_sink(tmp_path: Path) -> None:
    sink = FileLogSink(tmp_path / "logs" / "runtime.jsonl")
    logger = StructuredLogger(sink=sink)
    logger.log(
        level=LogLevel.INFO,
        event="runtime.event",
        message="export me",
        correlation_id="corr_export",
        context={"job_id": "job_2"},
    )
    exported = (tmp_path / "logs" / "runtime.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(exported) == 1
    payload = json.loads(exported[0])
    assert payload["event"] == "runtime.event"
    assert payload["correlation_id"] == "corr_export"


def test_logger_fallback_keeps_record_when_sink_fails() -> None:
    class FailingSink:
        def emit(self, record) -> None:  # pragma: no cover - called by logger
            raise RuntimeError("sink down")

    logger = StructuredLogger(sink=FailingSink(), fallback_to_memory=True)
    logger.log(
        level=LogLevel.WARNING,
        event="runtime.warn",
        message="fallback",
        correlation_id="corr_fallback",
    )
    record = logger.records()[0]
    assert record.context["log_export_status"] == "failed"


def test_runtime_tracer_exports_spans_to_file(tmp_path: Path) -> None:
    tracer = RuntimeTracer(exporter=FileTraceExporter(tmp_path / "traces" / "spans.jsonl"))
    span_id = tracer.start_span(correlation_id="corr_trace", name="scheduler.execute")
    tracer.finish_span(span_id=span_id, status="ok")
    exported = (tmp_path / "traces" / "spans.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(exported) == 1
    payload = json.loads(exported[0])
    assert payload["correlation_id"] == "corr_trace"
    assert payload["status"] == "ok"


def test_runtime_tracer_fallback_keeps_span_when_exporter_fails() -> None:
    class FailingExporter:
        def export(self, span) -> None:  # pragma: no cover - called by tracer
            raise RuntimeError("export down")

    tracer = RuntimeTracer(exporter=FailingExporter(), fallback_to_memory=True)
    span_id = tracer.start_span(correlation_id="corr_fallback", name="scheduler.execute")
    tracer.finish_span(span_id=span_id, status="ok")
    span = tracer.spans_for("corr_fallback")[0]
    assert span.attributes["trace_export_status"] == "failed"
