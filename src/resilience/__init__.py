"""
File: __init__.py
Path: src/resilience/__init__.py
Role: Public exports for resilience components.
Used By:
 - src/core/scheduler.py
 - src/mcp/mcp_tool_adapter.py
Depends On:
 - src/resilience/retry_policy.py
 - src/resilience/circuit_breaker.py
 - src/resilience/dlq.py
 - src/resilience/compensation_hooks.py
Notes:
 - Keep resilience APIs composable and optional by default.
"""

from src.resilience.circuit_breaker import CircuitBreaker
from src.resilience.compensation_hooks import CompensationHooks
from src.resilience.dlq import DeadLetterQueue, DlqRecord
from src.resilience.retry_policy import RetryPolicy

__all__ = ["RetryPolicy", "CircuitBreaker", "DeadLetterQueue", "DlqRecord", "CompensationHooks"]

