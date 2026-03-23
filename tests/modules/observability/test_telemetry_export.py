"""
File: test_telemetry_export.py
Path: tests/modules/observability/test_telemetry_export.py
Role: Unit tests for optional OTLP exporter bootstrap.
Used By:
 - pytest
Depends On:
 - src/observability/telemetry_export.py
Notes:
 - Does not require a running collector; avoids setting OTEL_EXPORTER_OTLP_* by default.
"""

from __future__ import annotations

import builtins
from unittest.mock import MagicMock, patch

import pytest

from src.observability import telemetry_export as te
from src.observability.telemetry_export import build_minimal_prometheus_text, configure_opentelemetry_exporters


def test_configure_opentelemetry_exporters_no_env_is_noop() -> None:
    configure_opentelemetry_exporters()


def test_build_minimal_prometheus_text_contains_metric() -> None:
    body = build_minimal_prometheus_text()
    assert "exo_build_info" in body
    assert "service=" in body


def test_traces_endpoint_prefers_explicit_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "http://collector/traces-only")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector")
    assert te._traces_endpoint() == "http://collector/traces-only"


def test_traces_endpoint_builds_from_base_when_implicit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector/")
    assert te._traces_endpoint() == "http://collector/v1/traces"


def test_metrics_endpoint_prefers_explicit_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_METRICS_ENDPOINT", "http://collector/metrics-only")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector")
    assert te._metrics_endpoint() == "http://collector/metrics-only"


def test_metrics_endpoint_builds_from_base_when_implicit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_METRICS_ENDPOINT", raising=False)
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector")
    assert te._metrics_endpoint() == "http://collector/v1/metrics"


def test_configure_opentelemetry_logs_on_import_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://127.0.0.1:9")

    real_import = builtins.__import__

    def _block_otel(name: str, globals_=None, locals_=None, fromlist=(), level: int = 0):
        if name == "opentelemetry" or name.startswith("opentelemetry."):
            raise ImportError("blocked for test")
        return real_import(name, globals_, locals_, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _block_otel)
    configure_opentelemetry_exporters()


def test_configure_opentelemetry_trace_only_invokes_tracer_branch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_METRICS_ENDPOINT", raising=False)
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "http://127.0.0.1:65533/v1/traces")

    tp_instance = MagicMock()
    with (
        patch("opentelemetry.sdk.trace.TracerProvider", return_value=tp_instance),
        patch("opentelemetry.sdk.trace.export.BatchSpanProcessor"),
        patch("opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter"),
        patch("opentelemetry.trace.set_tracer_provider") as set_tp,
        patch("opentelemetry.metrics.set_meter_provider") as set_mp,
    ):
        configure_opentelemetry_exporters()
    set_tp.assert_called_once_with(tp_instance)
    tp_instance.add_span_processor.assert_called_once()
    set_mp.assert_not_called()


def test_configure_opentelemetry_metrics_only_invokes_metrics_branch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_METRICS_ENDPOINT", "http://127.0.0.1:65532/v1/metrics")
    monkeypatch.setenv("OTEL_METRIC_EXPORT_INTERVAL_MS", "86400000")

    mp_instance = MagicMock()
    with (
        patch("opentelemetry.sdk.metrics.MeterProvider", return_value=mp_instance),
        patch("opentelemetry.sdk.metrics.export.PeriodicExportingMetricReader"),
        patch("opentelemetry.exporter.otlp.proto.http.metric_exporter.OTLPMetricExporter"),
        patch("opentelemetry.metrics.set_meter_provider") as set_mp,
        patch("opentelemetry.trace.set_tracer_provider") as set_tp,
    ):
        configure_opentelemetry_exporters()
    set_mp.assert_called_once_with(mp_instance)
    set_tp.assert_not_called()


def test_configure_opentelemetry_wires_both_when_base_endpoint_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://127.0.0.1:65531")
    monkeypatch.setenv("OTEL_SERVICE_NAME", "pytest-exo")
    monkeypatch.setenv("OTEL_METRIC_EXPORT_INTERVAL_MS", "86400000")

    tp_instance = MagicMock()
    mp_instance = MagicMock()
    with (
        patch("opentelemetry.sdk.trace.TracerProvider", return_value=tp_instance),
        patch("opentelemetry.sdk.trace.export.BatchSpanProcessor"),
        patch("opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter"),
        patch("opentelemetry.sdk.metrics.MeterProvider", return_value=mp_instance),
        patch("opentelemetry.sdk.metrics.export.PeriodicExportingMetricReader"),
        patch("opentelemetry.exporter.otlp.proto.http.metric_exporter.OTLPMetricExporter"),
        patch("opentelemetry.trace.set_tracer_provider") as set_tp,
        patch("opentelemetry.metrics.set_meter_provider") as set_mp,
    ):
        configure_opentelemetry_exporters()
    set_tp.assert_called_once_with(tp_instance)
    set_mp.assert_called_once_with(mp_instance)
    tp_instance.add_span_processor.assert_called_once()
