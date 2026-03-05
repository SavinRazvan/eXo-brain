"""
File: test_circuit_breaker_behavior.py
Path: tests/modules/resilience/test_circuit_breaker_behavior.py
Role: Unit tests for circuit breaker state transitions.
Used By:
 - pytest
Depends On:
 - src/resilience/circuit_breaker.py
Notes:
 - Confirms repeated failures open the circuit.
"""

from src.resilience.circuit_breaker import CircuitBreaker


def test_circuit_breaker_opens_after_threshold_failures() -> None:
    breaker = CircuitBreaker(failure_threshold=2)
    assert breaker.allow("srv:tool") is True
    breaker.record_failure("srv:tool")
    assert breaker.allow("srv:tool") is True
    breaker.record_failure("srv:tool")
    assert breaker.allow("srv:tool") is False


def test_circuit_breaker_record_success_resets_open_state() -> None:
    breaker = CircuitBreaker(failure_threshold=2)
    breaker.record_failure("srv:tool")
    breaker.record_failure("srv:tool")
    assert breaker.allow("srv:tool") is False
    breaker.record_success("srv:tool")
    assert breaker.allow("srv:tool") is True


def test_circuit_breaker_state_isolated_per_key() -> None:
    breaker = CircuitBreaker(failure_threshold=1)
    breaker.record_failure("srv:a")
    assert breaker.allow("srv:a") is False
    assert breaker.allow("srv:b") is True

