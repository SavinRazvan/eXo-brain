"""
File: slo_registry.py
Path: src/observability/slo_registry.py
Role: SLO target registry used by quality-gate evaluation.
Used By:
 - src/observability/gate_evaluator.py
Depends On:
 - dataclasses
Notes:
 - Baseline focuses on a compact key/value target map.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class SloRegistry:
    targets: dict[str, float] = field(default_factory=dict)

    def set_target(self, key: str, value: float) -> None:
        self.targets[key] = value

    def get_target(self, key: str) -> float | None:
        return self.targets.get(key)

