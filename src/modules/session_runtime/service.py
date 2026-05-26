"""
File: service.py
Path: src/modules/session_runtime/service.py
Role: Public module service for tenant context lookup, session creation, and runtime-control ownership.
Used By:
 - src/modules/platform_bootstrap/service.py
 - src/api/dependencies.py
 - src/api/routers/sessions.py
 - src/api/routers/runtime_control.py
 - src/api/routers/turns.py
Depends On:
 - src/core/run_control_registry.py
 - src/core/session_context.py
 - src/persistence/contracts.py
 - src/runtime/tenant_runtime.py
 - src/tenancy/rate_limiter.py
Notes:
 - This facade keeps routers off the raw `TenantRuntimeFactory` and session-store wiring.
"""

from __future__ import annotations

from dataclasses import dataclass
import uuid

from src.core.run_control_registry import RunControlRegistry, SQLiteRunControlRegistry
from src.core.session_context import SessionContext
from src.identity.contracts import IdentityContext
from src.persistence.contracts import SessionRecord, SessionStore
from src.runtime.tenant_runtime import TenantRuntimeContext, TenantRuntimeFactory
from src.tenancy.rate_limiter import SQLiteTenantRateLimiter, TenantRateLimiter


@dataclass(frozen=True, slots=True)
class SessionRuntimeError(Exception):
    status_code: int
    detail: str

    def __str__(self) -> str:
        return self.detail


@dataclass(slots=True)
class SessionRuntimeService:
    tenant_factory: TenantRuntimeFactory
    session_store: SessionStore | None
    run_control_registry: RunControlRegistry | SQLiteRunControlRegistry
    turn_rate_limiter: TenantRateLimiter | SQLiteTenantRateLimiter
    tool_upload_rate_limiter: TenantRateLimiter | SQLiteTenantRateLimiter

    def get_tenant_context(self, tenant_id: str) -> TenantRuntimeContext:
        return self.tenant_factory.get_or_create(tenant_id)

    async def create_session(
        self,
        *,
        tenant_id: str,
        agent_id: str,
        provider_id: str,
        correlation_id: str | None,
        identity: IdentityContext,
    ) -> SessionContext:
        if self.session_store is None:
            raise SessionRuntimeError(status_code=503, detail="Session store is not configured on this server.")

        session_id = f"sess_{uuid.uuid4().hex}"
        resolved_correlation_id = str(correlation_id or session_id)
        tenant_context = self.get_tenant_context(tenant_id)
        try:
            self.tenant_factory.create_session_runtime(
                tenant_context=tenant_context,
                agent_id=agent_id,
                provider_id=provider_id,
                session_id=session_id,
            )
        except KeyError as exc:
            raise SessionRuntimeError(status_code=404, detail=str(exc)) from exc

        session_ctx = SessionContext(
            session_id=session_id,
            run_id=f"run_{uuid.uuid4().hex[:8]}",
            job_id=f"job_{uuid.uuid4().hex[:8]}",
            task_id=f"task_{uuid.uuid4().hex[:8]}",
            agent_id=agent_id,
            provider_id=provider_id,
            correlation_id=resolved_correlation_id,
            identity=identity,
            metadata={
                "agent_id": agent_id,
                "provider_id": provider_id,
                "correlation_id": resolved_correlation_id,
            },
        )
        await tenant_context.session_store.save_session(
            SessionRecord(
                session=session_ctx,
                tenant_id=tenant_id,
                state="active",
                data={
                    "agent_id": agent_id,
                    "provider_id": provider_id,
                    "correlation_id": resolved_correlation_id,
                },
            )
        )
        return session_ctx

    async def get_session(self, *, tenant_id: str, session_id: str) -> SessionRecord | None:
        if self.session_store is None:
            raise SessionRuntimeError(status_code=503, detail="Session store is not configured on this server.")
        tenant_context = self.get_tenant_context(tenant_id)
        return await tenant_context.session_store.get_session(session_id, tenant_id=tenant_id)


@dataclass(slots=True)
class SessionRuntimeModule:
    service: SessionRuntimeService
    tenant_factory: TenantRuntimeFactory
    session_store: SessionStore | None
    run_control_registry: RunControlRegistry | SQLiteRunControlRegistry
    turn_rate_limiter: TenantRateLimiter | SQLiteTenantRateLimiter
    tool_upload_rate_limiter: TenantRateLimiter | SQLiteTenantRateLimiter
