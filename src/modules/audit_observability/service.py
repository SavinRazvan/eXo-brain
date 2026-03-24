"""
File: service.py
Path: src/modules/audit_observability/service.py
Role: Public module facade for audit storage, audit pipeline, and local observability sinks.
Used By:
 - src/modules/platform_bootstrap/service.py
 - src/api/routers/audit.py
 - src/api/routers/turns.py
 - src/api/routers/runtime_control.py
Depends On:
 - src/observability/ingress_budget.py
 - src/observability/logging.py
 - src/observability/tool_audit.py
 - src/persistence/contracts.py
Notes:
 - Standard telemetry export can be added behind this module without changing routers.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.observability.ingress_budget import IngressBudgetRecorder
from src.observability.logging import StructuredLogger
from src.observability.tool_audit import ToolAuditPipeline
from src.persistence.contracts import AuditStore


@dataclass(frozen=True, slots=True)
class AuditObservabilityError(Exception):
    status_code: int
    detail: str

    def __str__(self) -> str:
        return self.detail


@dataclass(slots=True)
class AuditObservabilityModule:
    audit_store: AuditStore | None
    tool_audit_pipeline: ToolAuditPipeline | None
    structured_logger: StructuredLogger | None
    ingress_budget_recorder: IngressBudgetRecorder | None
    audit_export_directory: Path
    max_audit_records_per_tenant: int
    max_audit_export_records: int
    audit_bundle_signing_secret: str
    audit_bundle_signing_active_version: str
    audit_bundle_signing_secrets_by_version: dict[str, str]

    def require_audit_store(self) -> AuditStore:
        if self.audit_store is None:
            raise AuditObservabilityError(status_code=503, detail="Audit store is not configured.")
        return self.audit_store

    def ensure_export_directory(self) -> Path:
        self.audit_export_directory.mkdir(parents=True, exist_ok=True)
        return self.audit_export_directory.resolve()
