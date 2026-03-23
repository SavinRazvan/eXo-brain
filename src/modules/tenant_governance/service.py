"""
File: service.py
Path: src/modules/tenant_governance/service.py
Role: Public module facade for tenant policy overlays and request governance controls.
Used By:
 - src/modules/platform_bootstrap/service.py
 - src/api/routers/turns.py
Depends On:
 - src/tenancy/policy_overlay.py
Notes:
 - This facade keeps governance state retrieval behind one module-owned surface.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.tenancy.policy_overlay import TenantPolicyOverlayStore


@dataclass(slots=True)
class TenantGovernanceModule:
    policy_overlay_store: TenantPolicyOverlayStore
    turn_rate_limiter: Any
    tool_upload_rate_limiter: Any

    def overlay_for_tenant(self, tenant_id: str) -> dict[str, Any]:
        return dict(self.policy_overlay_store.get_overlay(tenant_id))
