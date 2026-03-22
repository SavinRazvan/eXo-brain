"""
File: test_gate_evaluator.py
Path: tests/modules/observability/test_gate_evaluator.py
Role: Unit tests for SLO gate evaluation branches (missing metrics, threshold breach).
Used By:
 - pytest
Depends On:
 - src/observability/gate_evaluator.py
 - src/observability/slo_registry.py
Notes:
 - Keeps release guardrail inputs deterministic.
"""

from src.observability.gate_evaluator import evaluate_gates
from src.observability.slo_registry import SloRegistry


def test_evaluate_gates_fails_when_observed_metric_missing() -> None:
    registry = SloRegistry()
    registry.set_target("latency_p95_ms", 100.0)
    report = evaluate_gates(registry, {})
    assert report.passed is False
    assert "latency_p95_ms" in report.failed_keys


def test_slo_registry_get_target_returns_none_for_unknown_key() -> None:
    registry = SloRegistry()
    assert registry.get_target("missing_metric") is None


def test_evaluate_gates_fails_when_value_exceeds_target() -> None:
    registry = SloRegistry()
    registry.set_target("error_rate", 0.01)
    report = evaluate_gates(registry, {"error_rate": 0.05})
    assert report.passed is False
    assert "error_rate" in report.failed_keys
