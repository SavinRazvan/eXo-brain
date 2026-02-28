"""
File: retry_policy.py
Path: src/resilience/retry_policy.py
Role: Retry delay policy helpers for bounded retry behavior.
Used By:
 - src/core/scheduler.py
Depends On:
 - dataclasses
Notes:
 - Exponential delays are bounded to avoid runaway waits.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class RetryPolicy:
    base_delay_ms: int = 50
    max_delay_ms: int = 1000

    def delay_seconds(self, attempt: int) -> float:
        attempt = max(1, attempt)
        delay_ms = min(self.base_delay_ms * (2 ** (attempt - 1)), self.max_delay_ms)
        return delay_ms / 1000.0

