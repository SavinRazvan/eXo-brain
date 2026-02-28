"""
File: decorators.py
Path: src/tools/decorators.py
Role: Decorator hooks for deterministic tool execution (validation, authz, retries, audit, redaction).
Used By:
 - src/tools/executor.py
 - src/tools/plugins/plugin_manager.py
Depends On:
 - functools
Notes:
 - These decorators are policy-adjacent execution hooks, not policy ownership.
"""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable

ToolHandler = Callable[..., Any]
AuditSink = Callable[[dict[str, Any]], None]


def validation(required_args: list[str]) -> Callable[[ToolHandler], ToolHandler]:
    def decorate(fn: ToolHandler) -> ToolHandler:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            missing = [name for name in required_args if name not in kwargs]
            if missing:
                raise ValueError(f"Missing required arguments: {missing}")
            return fn(*args, **kwargs)

        return wrapper

    return decorate


def authz(allow_state_changing: bool, is_state_changing_call: bool) -> Callable[[ToolHandler], ToolHandler]:
    def decorate(fn: ToolHandler) -> ToolHandler:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if is_state_changing_call and not allow_state_changing:
                raise PermissionError("State-changing execution is not authorized for this tool")
            return fn(*args, **kwargs)

        return wrapper

    return decorate


def retries(max_attempts: int) -> Callable[[ToolHandler], ToolHandler]:
    safe_attempts = max(1, max_attempts)

    def decorate(fn: ToolHandler) -> ToolHandler:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_error: Exception | None = None
            for _ in range(safe_attempts):
                try:
                    return fn(*args, **kwargs)
                except Exception as exc:  # pragma: no cover - simple retry loop
                    last_error = exc
            assert last_error is not None
            raise last_error

        return wrapper

    return decorate


def audit_logging(audit_sink: AuditSink | None, event_prefix: str) -> Callable[[ToolHandler], ToolHandler]:
    def decorate(fn: ToolHandler) -> ToolHandler:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if audit_sink is not None:
                audit_sink({"event": f"{event_prefix}.start"})
            try:
                value = fn(*args, **kwargs)
                if audit_sink is not None:
                    audit_sink({"event": f"{event_prefix}.success"})
                return value
            except Exception as exc:
                if audit_sink is not None:
                    audit_sink({"event": f"{event_prefix}.error", "message": str(exc)})
                raise

        return wrapper

    return decorate


def redaction(redact_keys: list[str]) -> Callable[[ToolHandler], ToolHandler]:
    def decorate(fn: ToolHandler) -> ToolHandler:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            value = fn(*args, **kwargs)
            if not isinstance(value, dict):
                return value
            redacted = dict(value)
            for key in redact_keys:
                if key in redacted:
                    redacted[key] = "***REDACTED***"
            return redacted

        return wrapper

    return decorate


def apply_execution_decorators(
    handler: ToolHandler,
    *,
    required_args: list[str],
    allow_state_changing: bool,
    is_state_changing_call: bool,
    max_attempts: int,
    redact_keys: list[str],
    audit_sink: AuditSink | None,
    event_prefix: str,
) -> ToolHandler:
    decorated = handler
    decorated = validation(required_args)(decorated)
    decorated = authz(allow_state_changing=allow_state_changing, is_state_changing_call=is_state_changing_call)(decorated)
    decorated = retries(max_attempts=max_attempts)(decorated)
    decorated = audit_logging(audit_sink=audit_sink, event_prefix=event_prefix)(decorated)
    decorated = redaction(redact_keys)(decorated)
    return decorated
