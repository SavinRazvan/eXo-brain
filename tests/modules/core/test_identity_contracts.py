"""
File: test_identity_contracts.py
Path: tests/modules/core/test_identity_contracts.py
Role: Unit tests for identity contract parsing and session context wiring.
Used By:
 - pytest
Depends On:
 - src/core/session_context.py
 - src/identity/contracts.py
 - src/identity/resolver.py
Notes:
 - Keeps identity rollout backward-compatible and deterministic.
"""

from src.core.session_context import SessionContext
from src.identity.contracts import ActorType
from src.identity.resolver import resolve_identity


def test_resolve_identity_parses_valid_payload() -> None:
    identity = resolve_identity(
        {
            "subject": "user_123",
            "actor_type": "service",
            "roles": ["admin", "operator"],
            "tenant_id": "tenant_a",
            "token_id": "token_xyz",
        }
    )
    assert identity is not None
    assert identity.subject == "user_123"
    assert identity.actor_type == ActorType.SERVICE
    assert identity.roles == ["admin", "operator"]
    assert identity.tenant_id == "tenant_a"
    assert identity.token_id == "token_xyz"


def test_session_context_from_runtime_context_resolves_identity() -> None:
    context = SessionContext.from_runtime_context(
        session_id="sess_1",
        context={
            "run_id": "run_1",
            "job_id": "job_1",
            "task_id": "task_1",
            "agent_id": "agent_1",
            "provider_id": "provider_1",
            "identity": {"subject": "user_456", "roles": ["viewer"]},
            "session_metadata": {"source": "unit"},
        },
    )
    assert context.identity is not None
    assert context.identity.subject == "user_456"
    assert context.identity.roles == ["viewer"]
