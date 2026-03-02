"""
File: quotas.py
Path: src/tenancy/quotas.py
Role: Tenant quota checks for background runtime submissions.
Used By:
 - src/core/background_runtime.py
Depends On:
 - dataclasses
Notes:
 - Can operate in soft mode for staged enforcement.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class QuotaDecision:
    allowed: bool
    reason_code: str = ""
    message: str = ""


class TenantQuotaManager:
    def __init__(self, max_active_jobs_per_tenant: int = 0, hard_enforcement: bool = True) -> None:
        self._max_active_jobs_per_tenant = max_active_jobs_per_tenant
        self._hard_enforcement = hard_enforcement

    @property
    def max_active_jobs(self) -> int:
        """Return current configured limit (0 means unlimited)."""
        return self._max_active_jobs_per_tenant

    def set_limit(self, max_active_jobs: int) -> None:
        """Update the active job limit. Takes effect on the next check_submission call."""
        if max_active_jobs < 0:
            raise ValueError("max_active_jobs must be >= 0 (0 = unlimited)")
        self._max_active_jobs_per_tenant = max_active_jobs

    def check_submission(self, tenant_id: str, active_jobs: int) -> QuotaDecision:
        if self._max_active_jobs_per_tenant <= 0:
            return QuotaDecision(allowed=True)
        if active_jobs < self._max_active_jobs_per_tenant:
            return QuotaDecision(allowed=True)
        if not self._hard_enforcement:
            return QuotaDecision(
                allowed=True,
                reason_code="TENANT_QUOTA_SOFT_LIMIT",
                message=f"Tenant '{tenant_id}' exceeded soft quota limit.",
            )
        return QuotaDecision(
            allowed=False,
            reason_code="TENANT_QUOTA_EXCEEDED",
            message=f"Tenant '{tenant_id}' exceeded max active jobs quota.",
        )

