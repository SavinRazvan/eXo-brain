"""
File: circuit_breaker.py
Path: src/resilience/circuit_breaker.py
Role: Lightweight circuit breaker for repeated failure protection.
Used By:
 - src/mcp/mcp_tool_adapter.py
Depends On:
 - dataclasses
Notes:
 - One breaker instance can track multiple keys (tool/server IDs).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class CircuitState:
    failures: int = 0
    open: bool = False


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 3) -> None:
        self._failure_threshold = max(1, failure_threshold)
        self._states: dict[str, CircuitState] = {}

    def allow(self, key: str) -> bool:
        state = self._states.get(key)
        return state is None or not state.open

    def record_success(self, key: str) -> None:
        self._states[key] = CircuitState(failures=0, open=False)

    def record_failure(self, key: str) -> None:
        state = self._states.setdefault(key, CircuitState())
        state.failures += 1
        if state.failures >= self._failure_threshold:
            state.open = True

