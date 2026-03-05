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
import json
from pathlib import Path
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


class LogSink:
    def emit(self, record: LogRecord) -> None:
        raise NotImplementedError


class FileLogSink(LogSink):
    """JSONL sink for structured log export."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, record: LogRecord) -> None:
        payload = {
            "timestamp_utc": record.timestamp_utc,
            "level": record.level.value,
            "event": record.event,
            "message": record.message,
            "correlation_id": record.correlation_id,
            "tenant_id": record.tenant_id,
            "context": record.context,
        }
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")


class StructuredLogger:
    def __init__(self, sink: LogSink | None = None, *, fallback_to_memory: bool = True) -> None:
        self._sink = sink
        self._fallback_to_memory = fallback_to_memory
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
        record = LogRecord(
            level=level,
            event=event,
            message=message,
            correlation_id=correlation_id,
            tenant_id=tenant_id,
            context=_redact_context(dict(context or {})),
        )
        self._records.append(record)
        if self._sink is not None:
            try:
                self._sink.emit(record)
            except Exception as exc:
                if self._fallback_to_memory:
                    record.context = {
                        **record.context,
                        "log_export_status": "failed",
                        "log_export_error": str(exc),
                    }
                else:
                    raise

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
