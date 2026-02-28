"""
File: test_retry_idempotency_guards.py
Path: tests/resilience/test_retry_idempotency_guards.py
Role: Unit tests for retry delay policy bounds.
Used By:
 - pytest
Depends On:
 - src/resilience/retry_policy.py
Notes:
 - Bounded exponential policy avoids unbounded delays.
"""

from src.resilience.retry_policy import RetryPolicy


def test_retry_policy_delay_is_bounded_and_increasing() -> None:
    policy = RetryPolicy(base_delay_ms=10, max_delay_ms=40)
    d1 = policy.delay_seconds(1)
    d2 = policy.delay_seconds(2)
    d3 = policy.delay_seconds(3)
    assert d1 < d2 <= d3
    assert d3 == 0.04

