"""
File: tenant_context.py
Path: src/tenancy/tenant_context.py
Role: Tenant context contract for runtime and policy scoping.
Used By:
 - src/core/background_runtime.py
 - src/tenancy/quotas.py
Depends On:
 - dataclasses
Notes:
 - Default tenant is `default` for backward compatibility.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class TenantContext:
    tenant_id: str = "default"

