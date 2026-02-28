"""
File: __init__.py
Path: src/identity/__init__.py
Role: Public identity module exports.
Used By:
 - src/core/session_context.py
 - tests/unit/test_identity_contracts.py
Depends On:
 - src/identity/contracts.py
 - src/identity/resolver.py
Notes:
 - Keep exports stable for downstream modules.
"""

from src.identity.contracts import ActorType, IdentityContext
from src.identity.resolver import resolve_identity

__all__ = ["ActorType", "IdentityContext", "resolve_identity"]

