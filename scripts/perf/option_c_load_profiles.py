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
import json
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

    @property
    def rejection_ratio(self) -> float:
        if self.total_requests <= 0:
            return 0.0
        rejected = self.rejected_rate + self.rejected_concurrency
        return float(rejected) / float(self.total_requests)


def _load_thresholds(path: str) -> dict[str, float]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return {
        "max_p95_wait_ms": float(payload.get("max_p95_wait_ms", 300.0)),
        "max_rejection_ratio": float(payload.get("max_rejection_ratio", 0.05)),
        "max_starvation_tenants": float(payload.get("max_starvation_tenants", 0)),
    }


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
    parser.add_argument("--json-out", default="", help="Optional path for structured profile output.")
    parser.add_argument("--enforce", action="store_true", help="Fail when any profile breaches thresholds.")
    parser.add_argument(
        "--thresholds-json",
        default="configs/release/option_c_slo_thresholds.json",
        help="JSON file with max_p95_wait_ms, max_rejection_ratio, max_starvation_tenants.",
    )
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

    structured = [
        {
            "profile": row.profile,
            "total_requests": row.total_requests,
            "allowed": row.allowed,
            "rejected_rate": row.rejected_rate,
            "rejected_concurrency": row.rejected_concurrency,
            "p95_wait_ms": row.p95_wait_ms,
            "starvation_tenants": row.starvation_tenants,
            "rejection_ratio": round(row.rejection_ratio, 6),
        }
        for row in results
    ]
    if args.json_out:
        out_path = Path(args.json_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps({"profiles": structured}, indent=2), encoding="utf-8")

    if not args.enforce:
        return 0

    thresholds = _load_thresholds(args.thresholds_json)
    failed: list[str] = []
    for row in results:
        if row.p95_wait_ms > thresholds["max_p95_wait_ms"]:
            failed.append(f"{row.profile}:p95_wait_ms")
        if row.rejection_ratio > thresholds["max_rejection_ratio"]:
            failed.append(f"{row.profile}:rejection_ratio")
        if row.starvation_tenants > int(thresholds["max_starvation_tenants"]):
            failed.append(f"{row.profile}:starvation_tenants")
    if failed:
        print(f"SLO_ENFORCEMENT_FAILED: {', '.join(failed)}")
        return 1
    print("SLO_ENFORCEMENT_PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

