"""
File: rbac.py
Path: src/access_control/rbac.py
Role: RBAC permission resolution helpers.
Used By:
 - src/access_control/policy_engine.py
Depends On:
 - none
Notes:
 - Supports wildcard permission `*` for admin-style roles.
"""

from __future__ import annotations


def aggregate_permissions(
    roles: list[str],
    role_permissions: dict[str, set[str]],
) -> set[str]:
    permissions: set[str] = set()
    for role in roles:
        permissions.update(role_permissions.get(role, set()))
    return permissions

