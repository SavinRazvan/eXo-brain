"""
File: test_release_guardrails.py
Path: tests/modules/observability/test_release_guardrails.py
Role: Unit tests for quality-gate evaluator and release guardrail decisions.
Used By:
 - pytest
Depends On:
 - src/observability/slo_registry.py
 - src/observability/gate_evaluator.py
 - src/policies/release_guardrails.py
Notes:
 - Fails closed when required evidence is missing.
"""

from src.observability.gate_evaluator import evaluate_gates
from src.observability.slo_registry import SloRegistry
from src.policies.release_guardrails import can_release


def test_release_guardrails_require_passing_report_and_required_gates() -> None:
    registry = SloRegistry()
    registry.set_target("latency_p95_ms", 3000.0)
    report = evaluate_gates(registry, {"latency_p95_ms": 2500.0})
    assert can_release(report, required_gates_present=True) is True
    assert can_release(report, required_gates_present=False) is False

