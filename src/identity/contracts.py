"""
File: contracts.py
Path: src/identity/contracts.py
Role: Identity contracts shared across integration, orchestration, and policy decisions.
Used By:
 - src/identity/resolver.py
 - src/core/session_context.py
 - src/integration/host_adapter.py
Depends On:
 - dataclasses
Notes:
 - Keep identity payload minimal and provider-neutral.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ActorType(str, Enum):
    HUMAN = "human"
    SERVICE = "service"


class TokenValidationState(str, Enum):
    UNKNOWN = "unknown"
    VALID = "valid"
    INVALID = "invalid"
    EXPIRED = "expired"
    ROTATION_REQUIRED = "rotation_required"


@dataclass(slots=True)
class IdentityContext:
    subject: str
    actor_type: ActorType = ActorType.HUMAN
    roles: list[str] = field(default_factory=list)
    tenant_id: str = "default"
    token_id: str = ""
    token_validation_state: TokenValidationState = TokenValidationState.UNKNOWN
    token_issued_at_utc: str = ""
    token_expires_at_utc: str = ""
    token_rotation_required: bool = False

