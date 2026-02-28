"""
File: metrics.py
Path: src/observability/metrics.py
Role: Minimal runtime metrics counters and latency observations.
Used By:
 - src/core/scheduler.py
 - src/core/background_runtime.py
Depends On:
 - dataclasses
Notes:
 - Metrics are intentionally simple; backends can scrape/bridge these values.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class RuntimeMetrics:
    counters: dict[str, int] = field(default_factory=dict)
    latency_ms: list[float] = field(default_factory=list)
    gauges: dict[str, float] = field(default_factory=dict)

    def inc(self, key: str, value: int = 1) -> None:
        self.counters[key] = self.counters.get(key, 0) + value

    def observe_latency(self, value_ms: float) -> None:
        self.latency_ms.append(value_ms)

    def set_gauge(self, key: str, value: float) -> None:
        self.gauges[key] = value

    def rate(self, numerator_key: str, denominator_key: str) -> float:
        denominator = self.counters.get(denominator_key, 0)
        if denominator <= 0:
            return 0.0
        numerator = self.counters.get(numerator_key, 0)
        return numerator / denominator
