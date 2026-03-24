"""
File: telemetry_export.py
Path: src/observability/telemetry_export.py
Role: Optional OpenTelemetry OTLP HTTP export for traces and metrics (no-op when unset).
Used By:
 - src/api/bootstrap.py
Depends On:
 - opentelemetry (optional; imported only when OTLP env is set)
Notes:
 - Uses OTEL_EXPORTER_OTLP_ENDPOINT as base URL when OTEL_EXPORTER_OTLP_TRACES_ENDPOINT /
   OTEL_EXPORTER_OTLP_METRICS_ENDPOINT are not provided.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def _base_otlp_endpoint() -> str:
    return str(os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "") or "").strip().rstrip("/")


def _traces_endpoint() -> str:
    explicit = str(os.environ.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "") or "").strip()
    if explicit:
        return explicit
    base = _base_otlp_endpoint()
    if not base:
        return ""
    return f"{base}/v1/traces"


def _metrics_endpoint() -> str:
    explicit = str(os.environ.get("OTEL_EXPORTER_OTLP_METRICS_ENDPOINT", "") or "").strip()
    if explicit:
        return explicit
    base = _base_otlp_endpoint()
    if not base:
        return ""
    return f"{base}/v1/metrics"


def configure_opentelemetry_exporters() -> None:
    """Configure OTLP HTTP trace and metric exporters when endpoints are configured."""
    traces_ep = _traces_endpoint()
    metrics_ep = _metrics_endpoint()
    if not traces_ep and not metrics_ep:
        return

    try:
        from opentelemetry import metrics as otel_metrics
        from opentelemetry import trace as otel_trace
        from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError as exc:
        logger.warning(
            "OpenTelemetry packages missing; install opentelemetry-sdk and OTLP HTTP exporters: %s",
            exc,
        )
        return

    resource = Resource.create(
        {
            "service.name": os.environ.get("OTEL_SERVICE_NAME", "exo-brain"),
            "service.version": os.environ.get("OTEL_SERVICE_VERSION", "0.1.0"),
        }
    )

    if traces_ep:
        tracer_provider = TracerProvider(resource=resource)
        tracer_provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=traces_ep)),
        )
        otel_trace.set_tracer_provider(tracer_provider)
        logger.info("OTLP trace exporter enabled: %s", traces_ep)

    if metrics_ep:
        reader = PeriodicExportingMetricReader(
            OTLPMetricExporter(endpoint=metrics_ep),
            export_interval_millis=int(os.environ.get("OTEL_METRIC_EXPORT_INTERVAL_MS", "60000")),
        )
        meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
        otel_metrics.set_meter_provider(meter_provider)
        logger.info("OTLP metrics exporter enabled: %s", metrics_ep)


def build_minimal_prometheus_text() -> str:
    """Return static process metadata in Prometheus text exposition format."""
    version = os.environ.get("OTEL_SERVICE_VERSION", "0.1.0").replace("\\", "").replace("\n", "")
    name = os.environ.get("OTEL_SERVICE_NAME", "exo-brain").replace("\\", "").replace("\n", "")
    lines = [
        "# HELP exo_build_info Build metadata for the eXo-brain process.",
        "# TYPE exo_build_info gauge",
        f'exo_build_info{{service="{name}",version="{version}"}} 1',
    ]
    return "\n".join(lines) + "\n"
