"""
File: option_c_load_profiles.py
Path: scripts/perf/option_c_load_profiles.py
Role: Lightweight 1/10/100-tenant load profile harness for Option C admission/fairness validation.
Used By:
 - Manual CLI runs before rollout decisions
Depends On:
 - src/tenancy/rate_limiter.py
 - src/core/agent_scaler.py
 - src/policies/byoc_fairness.py
Notes:
 - This is a deterministic simulation harness (not a full end-to-end network benchmark).
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

# Ensure repository root is importable when running as a script.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.core.agent_scaler import AgentScaler, AgentScalerConfig
from src.policies.byoc_fairness import ByocFairAdmissionCoordinator
from src.tenancy.rate_limiter import TenantRateLimiter


@dataclass(slots=True)
class ProfileResult:
    profile: str
    total_requests: int
    allowed: int
    rejected_rate: int
    rejected_concurrency: int
    p95_wait_ms: float
    starvation_tenants: int


def _simulate_profile(
    *,
    profile: str,
    tenant_count: int,
    requests_per_tenant: int,
    max_requests_per_minute: int,
    max_inflight_global: int,
) -> ProfileResult:
    limiter = TenantRateLimiter(max_requests=max_requests_per_minute, window_seconds=60)
    fair = ByocFairAdmissionCoordinator(max_inflight_global=max_inflight_global)
    scaler = AgentScaler(
        AgentScalerConfig(
            enabled=True,
            min_concurrency=1,
            max_concurrency=max(4, max_inflight_global),
            scale_up_backlog_threshold=2,
            backpressure_backlog_threshold=max(4, tenant_count // 2),
            backpressure_active_ratio_threshold=1.0,
        )
    )

    total_requests = tenant_count * requests_per_tenant
    allowed = 0
    rejected_rate = 0
    rejected_concurrency = 0
    wait_times_ms: list[float] = []
    per_tenant_grants: dict[str, int] = {f"tenant_{i:03d}": 0 for i in range(tenant_count)}

    # Deterministic round-robin traffic order across tenants.
    tenant_ids = list(per_tenant_grants.keys())
    active_jobs = 0
    pending_jobs = 0
    current_concurrency = max_inflight_global

    for request_idx in range(total_requests):
        tenant_id = tenant_ids[request_idx % tenant_count]
        rate_ok, _ = limiter.allow(tenant_id)
        if not rate_ok:
            rejected_rate += 1
            continue

        decision = scaler.evaluate(
            active_jobs=active_jobs,
            pending_jobs=pending_jobs,
            current_concurrency=current_concurrency,
        )
        current_concurrency = max(decision.target_concurrency, 1)
        if decision.backpressure:
            rejected_concurrency += 1
            continue

        start = perf_counter()
        token = fair.acquire(tenant_id=tenant_id, wait_timeout_ms=30)
        wait_ms = (perf_counter() - start) * 1000.0
        wait_times_ms.append(wait_ms)
        if token is None:
            rejected_concurrency += 1
            continue

        allowed += 1
        per_tenant_grants[tenant_id] += 1
        active_jobs += 1
        # Immediate release keeps simulation bounded and deterministic.
        fair.release(token)
        active_jobs = max(active_jobs - 1, 0)

    wait_times_ms_sorted = sorted(wait_times_ms)
    if wait_times_ms_sorted:
        idx = max(int(len(wait_times_ms_sorted) * 0.95) - 1, 0)
        p95_wait_ms = wait_times_ms_sorted[idx]
    else:
        p95_wait_ms = 0.0
    starvation_tenants = sum(1 for grants in per_tenant_grants.values() if grants == 0)

    return ProfileResult(
        profile=profile,
        total_requests=total_requests,
        allowed=allowed,
        rejected_rate=rejected_rate,
        rejected_concurrency=rejected_concurrency,
        p95_wait_ms=round(p95_wait_ms, 2),
        starvation_tenants=starvation_tenants,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Option C load profile simulator (1/10/100 tenants).")
    parser.add_argument("--requests-per-tenant", type=int, default=120)
    parser.add_argument("--max-rpm", type=int, default=120)
    parser.add_argument("--max-inflight", type=int, default=8)
    args = parser.parse_args()

    profiles = [
        ("tenant-1", 1),
        ("tenant-10", 10),
        ("tenant-100", 100),
    ]
    results: list[ProfileResult] = []
    for profile_name, tenant_count in profiles:
        result = _simulate_profile(
            profile=profile_name,
            tenant_count=tenant_count,
            requests_per_tenant=max(args.requests_per_tenant, 1),
            max_requests_per_minute=max(args.max_rpm, 1),
            max_inflight_global=max(args.max_inflight, 1),
        )
        results.append(result)

    print("profile,total,allowed,rejected_rate,rejected_concurrency,p95_wait_ms,starvation_tenants")
    for row in results:
        print(
            f"{row.profile},{row.total_requests},{row.allowed},{row.rejected_rate},"
            f"{row.rejected_concurrency},{row.p95_wait_ms},{row.starvation_tenants}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

