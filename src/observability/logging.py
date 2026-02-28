"""
File: logging.py
Path: src/observability/logging.py
Role: Structured runtime logging contracts and in-memory logger implementation.
Used By:
 - src/core/scheduler.py
 - src/core/background_runtime.py
Depends On:
 - dataclasses
Notes:
 - Log records keep correlation IDs for deterministic timeline reconstruction.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class LogLevel(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(slots=True)
class LogRecord:
    level: LogLevel
    event: str
    message: str
    correlation_id: str
    tenant_id: str = "default"
    context: dict[str, Any] = field(default_factory=dict)
    timestamp_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class StructuredLogger:
    def __init__(self) -> None:
        self._records: list[LogRecord] = []

    def log(
        self,
        level: LogLevel,
        event: str,
        message: str,
        correlation_id: str,
        tenant_id: str = "default",
        context: dict[str, Any] | None = None,
    ) -> None:
        self._records.append(
            LogRecord(
                level=level,
                event=event,
                message=message,
                correlation_id=correlation_id,
                tenant_id=tenant_id,
                context=_redact_context(dict(context or {})),
            )
        )

    def records(self) -> list[LogRecord]:
        return list(self._records)


def _redact_context(context: dict[str, Any]) -> dict[str, Any]:
    redacted: dict[str, Any] = {}
    for key, value in context.items():
        lowered = key.lower()
        if "secret" in lowered or "token" in lowered or "password" in lowered or "api_key" in lowered:
            redacted[key] = "***REDACTED***"
        else:
            redacted[key] = value
    return redacted
