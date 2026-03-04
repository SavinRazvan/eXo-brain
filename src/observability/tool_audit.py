"""
File: tool_audit.py
Path: src/observability/tool_audit.py
Role: Emit structured and persisted audit events for tenant tool lifecycle actions.
Used By:
 - src/api/bootstrap.py
 - src/api/routers/tools.py
Depends On:
 - src/observability/logging.py
 - src/persistence/contracts.py
Notes:
 - Persisted audit entries are correlation-centric for deterministic traceability.
"""

from __future__ import annotations

import uuid
from typing import Any

from src.observability.logging import LogLevel, StructuredLogger
from src.persistence.contracts import AuditRecord, AuditStore


class ToolAuditPipeline:
    def __init__(
        self,
        *,
        logger: StructuredLogger | None = None,
        audit_store: AuditStore | None = None,
    ) -> None:
        self._logger = logger
        self._audit_store = audit_store

    async def emit(
        self,
        *,
        event_type: str,
        correlation_id: str,
        tenant_id: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        event_payload = dict(payload or {})
        if self._logger is not None:
            self._logger.log(
                level=LogLevel.INFO,
                event=f"tool.audit.{event_type}",
                message=f"Tool audit event: {event_type}",
                correlation_id=correlation_id,
                tenant_id=tenant_id,
                context=event_payload,
            )
        if self._audit_store is not None:
            await self._audit_store.append_audit_event(
                AuditRecord(
                    event_id=f"audit_{uuid.uuid4().hex[:12]}",
                    correlation_id=correlation_id,
                    tenant_id=tenant_id,
                    event_type=event_type,
                    payload=event_payload,
                )
            )
