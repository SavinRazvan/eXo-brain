"""
File: release_guardrails.py
Path: src/policies/release_guardrails.py
Role: Release guardrail checks based on gate evaluation reports.
Used By:
 - release workflow scripts (future)
 - tests/quality_gates/test_release_guardrails.py
Depends On:
 - src/observability/gate_evaluator.py
Notes:
 - Policy intentionally fails closed when required evidence is absent.
"""

from __future__ import annotations

from src.observability.gate_evaluator import GateReport


def can_release(report: GateReport, required_gates_present: bool) -> bool:
    if not required_gates_present:
        return False
    return report.passed

