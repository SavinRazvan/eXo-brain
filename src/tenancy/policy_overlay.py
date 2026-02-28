"""
File: policy_overlay.py
Path: src/tenancy/policy_overlay.py
Role: Tenant-level policy overlay storage and retrieval.
Used By:
 - src/core/background_runtime.py
Depends On:
 - none
Notes:
 - Overlay payload is intentionally generic to avoid coupling to policy internals.
"""

from __future__ import annotations

from typing import Any


class TenantPolicyOverlayStore:
    def __init__(self) -> None:
        self._overlays: dict[str, dict[str, Any]] = {}

    def set_overlay(self, tenant_id: str, overlay: dict[str, Any]) -> None:
        self._overlays[tenant_id] = dict(overlay)

    def get_overlay(self, tenant_id: str) -> dict[str, Any]:
        return dict(self._overlays.get(tenant_id, {}))

