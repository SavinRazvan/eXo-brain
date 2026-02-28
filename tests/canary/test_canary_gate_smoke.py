"""
File: test_canary_gate_smoke.py
Path: tests/canary/test_canary_gate_smoke.py
Role: Smoke test scaffold for canary gate evaluation behavior.
Used By:
 - pytest
Depends On:
 - src/observability/gate_evaluator.py
 - src/observability/slo_registry.py
Notes:
 - Baseline canary check compares observed latency/error against thresholds.
"""

from src.observability.gate_evaluator import evaluate_gates
from src.observability.slo_registry import SloRegistry


def test_canary_gate_smoke() -> None:
    registry = SloRegistry(targets={"latency_p95_ms": 3000.0, "error_rate": 0.05})
    report = evaluate_gates(registry, {"latency_p95_ms": 2900.0, "error_rate": 0.01})
    assert report.passed is True

