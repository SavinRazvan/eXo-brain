"""
File: gate_evaluator.py
Path: src/observability/gate_evaluator.py
Role: Evaluate quality gate metrics against configured SLO thresholds.
Used By:
 - src/policies/release_guardrails.py
Depends On:
 - src/observability/slo_registry.py
Notes:
 - Returns deterministic pass/fail report for release governance.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.observability.slo_registry import SloRegistry


@dataclass(slots=True)
class GateReport:
    passed: bool
    failed_keys: list[str] = field(default_factory=list)


def evaluate_gates(registry: SloRegistry, observed: dict[str, float]) -> GateReport:
    failed: list[str] = []
    for key, target in registry.targets.items():
        value = observed.get(key)
        if value is None:
            failed.append(key)
            continue
        if value > target:
            failed.append(key)
    return GateReport(passed=not failed, failed_keys=failed)

