"""
File: test_session_runtime_service.py
Path: tests/modules/session_runtime/test_session_runtime_service.py
Role: Unit tests for session-runtime service error handling branches.
Used By:
 - pytest
Depends On:
 - src/modules/session_runtime/service.py
Notes:
 - Covers unconfigured-store branches without routing through HTTP.
"""

from __future__ import annotations

import pytest

from src.identity.contracts import IdentityContext, TokenValidationState
from src.modules.session_runtime.service import SessionRuntimeError, SessionRuntimeService


class _FactoryDouble:
    def get_or_create(self, tenant_id: str):
        raise AssertionError(f"get_or_create should not be called for tenant {tenant_id}")


def _identity() -> IdentityContext:
    return IdentityContext(
        subject="user@example.com",
        tenant_id="tenant-a",
        roles=["platform_admin"],
        token_validation_state=TokenValidationState.VALID,
    )


def test_session_runtime_error_str_returns_detail() -> None:
    assert str(SessionRuntimeError(status_code=503, detail="session-missing")) == "session-missing"


@pytest.mark.asyncio
async def test_session_runtime_service_requires_configured_session_store() -> None:
    service = SessionRuntimeService(
        tenant_factory=_FactoryDouble(),  # type: ignore[arg-type]
        session_store=None,
        run_control_registry=None,
        turn_rate_limiter=None,
        tool_upload_rate_limiter=None,
    )

    with pytest.raises(SessionRuntimeError, match="Session store is not configured"):
        await service.create_session(
            tenant_id="tenant-a",
            agent_id="agent-a",
            provider_id="openai-test",
            correlation_id=None,
            identity=_identity(),
        )
    with pytest.raises(SessionRuntimeError, match="Session store is not configured"):
        await service.get_session(tenant_id="tenant-a", session_id="sess-1")
