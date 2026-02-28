"""
File: resolver.py
Path: src/identity/resolver.py
Role: Resolve identity context from host/runtime dictionaries.
Used By:
 - src/core/session_context.py
Depends On:
 - src/identity/contracts.py
Notes:
 - Returns None for invalid payloads so rollout can be non-breaking.
"""

from __future__ import annotations

from typing import Any

from src.identity.contracts import ActorType, IdentityContext


def resolve_identity(raw: Any) -> IdentityContext | None:
    if not isinstance(raw, dict):
        return None

    subject = str(raw.get("subject", "")).strip()
    if not subject:
        return None

    actor_raw = str(raw.get("actor_type", ActorType.HUMAN.value)).strip().lower()
    actor_type = ActorType(actor_raw) if actor_raw in {a.value for a in ActorType} else ActorType.HUMAN

    roles_raw = raw.get("roles", [])
    if isinstance(roles_raw, list):
        roles = [str(role).strip() for role in roles_raw if str(role).strip()]
    else:
        roles = []

    return IdentityContext(
        subject=subject,
        actor_type=actor_type,
        roles=roles,
        tenant_id=str(raw.get("tenant_id", "default")).strip() or "default",
        token_id=str(raw.get("token_id", "")).strip(),
    )

