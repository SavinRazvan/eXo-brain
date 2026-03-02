"""
File: auth.py
Path: src/api/middleware/auth.py
Role: Resolve IdentityContext from the X-Identity request header (MVP plain-JSON format).
Used By:
 - src/api/dependencies.py
Depends On:
 - src/identity/contracts.py
 - src/identity/resolver.py
Notes:
 - Decision 1: X-Identity carries a plain JSON dict for MVP.
 - JWT Bearer upgrade path: swap this file only. All downstream code only sees IdentityContext.
 - Returns None if the header is missing, malformed, or has no valid subject.
 - INVALID and EXPIRED token_validation_state values are rejected by require_valid_identity.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import Request

from src.identity.contracts import IdentityContext, TokenValidationState
from src.identity.resolver import resolve_identity

_HEADER_NAME = "X-Identity"


def extract_identity(request: Request) -> IdentityContext | None:
    """Parse X-Identity header and return an IdentityContext, or None if absent/invalid."""
    raw_header = request.headers.get(_HEADER_NAME)
    if not raw_header:
        return None
    try:
        payload: Any = json.loads(raw_header)
    except json.JSONDecodeError:
        return None
    return resolve_identity(payload)


def is_identity_usable(identity: IdentityContext) -> bool:
    """Return True only for VALID or UNKNOWN token states.

    INVALID and EXPIRED are explicitly rejected.
    ROTATION_REQUIRED is allowed through — callers are warned but not blocked.
    """
    rejected = {TokenValidationState.INVALID, TokenValidationState.EXPIRED}
    return identity.token_validation_state not in rejected
