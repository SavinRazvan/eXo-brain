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

from src.observability.telemetry_export import build_minimal_prometheus_text, configure_opentelemetry_exporters


def test_configure_opentelemetry_exporters_no_env_is_noop() -> None:
    configure_opentelemetry_exporters()


def test_build_minimal_prometheus_text_contains_metric() -> None:
    body = build_minimal_prometheus_text()
    assert "exo_build_info" in body
    assert "service=" in body
