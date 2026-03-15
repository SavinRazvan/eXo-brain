"""
File: ingress_budget_report.py
Path: scripts/perf/ingress_budget_report.py
Role: Deterministic ingress budget probe with per-profile SLO reporting and enforcement.
Used By:
 - scripts/release/verify_gates.py
Depends On:
 - src/observability/ingress_budget.py
 - src/policies/ingress_gates.py
Notes:
 - This is a local simulation harness and not a full transport benchmark.
 - Produces overall and per-profile (`baseline`, `strict`, `hardened`) SLO summaries.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Ensure repository root is importable when running as a script.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.observability.ingress_budget import IngressBudgetConfig, evaluate_with_budget, percentile
from src.policies.ingress_gates import IngressDecision
from src.schemas.tool_io import PolicyAction

PROFILE_PROBE_DELAYS_MS: tuple[tuple[str, int], ...] = (
    ("baseline", 0),
    ("strict", 1),
    ("hardened", 3),
)


def _allow_decision() -> IngressDecision:
    return IngressDecision(
        schema_version="1.0",
        decision=PolicyAction.ALLOW,
        reason_code="INGRESS_ALLOW_DEFAULT",
        message="Ingress baseline allowed.",
        gate_id="ingress-budget-probe",
        gate_version="1.0.0",
    )


async def _fast_eval() -> IngressDecision:
    return _allow_decision()


async def _slow_eval(delay_ms: int) -> IngressDecision:
    await asyncio.sleep(float(delay_ms) / 1000.0)
    return _allow_decision()


def _summary_from_observations(
    *,
    observations: list[object],
    budget_ms: int,
    timeout_ms: int,
    fail_mode: str,
) -> dict[str, object]:
    latencies = [float(getattr(observation, "latency_ms", 0.0)) for observation in observations]
    timeout_total = sum(1 for observation in observations if bool(getattr(observation, "timed_out", False)))
    samples = len(observations)
    return {
        "samples": samples,
        "p95_ingress_latency_ms": round(percentile(latencies, 0.95), 3),
        "timeout_total": timeout_total,
        "timeout_rate": round(float(timeout_total) / float(samples), 6) if samples > 0 else 0.0,
        "budget_ms": budget_ms,
        "timeout_ms": timeout_ms,
        "fail_mode": fail_mode,
    }


def _normalize_profile_name(value: str) -> str:
    normalized = str(value).strip().lower()
    return normalized or "baseline"


def _merge_reason_counts(existing: dict[str, int], incoming: dict[str, int]) -> dict[str, int]:
    merged = dict(existing)
    for reason_code, count in incoming.items():
        merged[reason_code] = merged.get(reason_code, 0) + int(count)
    return merged


async def _run_profile_probe(
    *,
    profile_name: str,
    nominal_delay_ms: int,
    samples: int,
    timeout_samples: int,
    budget_ms: int,
    timeout_ms: int,
    fail_mode: str,
) -> tuple[dict[str, object], list[object], dict[str, int]]:
    observations: list[object] = []
    reason_counts: dict[str, int] = {}
    profile = _normalize_profile_name(profile_name)
    config = IngressBudgetConfig(
        latency_budget_ms=budget_ms,
        timeout_ms=timeout_ms,
        timeout_fail_mode=fail_mode,
    )

    for _ in range(max(samples, 1)):
        decision, observation = await evaluate_with_budget(
            evaluate=(lambda: _slow_eval(nominal_delay_ms)) if nominal_delay_ms > 0 else _fast_eval,
            config=config,
            profile_name=profile,
        )
        observations.append(observation)
        reason_counts[decision.reason_code] = reason_counts.get(decision.reason_code, 0) + 1

    forced_timeout_delay_ms = max(timeout_ms + nominal_delay_ms + 10, 20)
    for _ in range(max(timeout_samples, 0)):
        decision, observation = await evaluate_with_budget(
            evaluate=lambda: _slow_eval(forced_timeout_delay_ms),
            config=config,
            profile_name=profile,
        )
        observations.append(observation)
        reason_counts[decision.reason_code] = reason_counts.get(decision.reason_code, 0) + 1

    return (
        {
            "profile": profile,
            "nominal_delay_ms": nominal_delay_ms,
            "forced_timeout_delay_ms": forced_timeout_delay_ms,
            "summary": _summary_from_observations(
                observations=observations,
                budget_ms=budget_ms,
                timeout_ms=timeout_ms,
                fail_mode=fail_mode,
            ),
            "reason_code_counts": reason_counts,
        },
        observations,
        reason_counts,
    )


async def _run_probe(
    *,
    samples: int,
    timeout_samples: int,
    budget_ms: int,
    timeout_ms: int,
    fail_mode: str,
) -> dict[str, object]:
    profile_reports: list[dict[str, object]] = []
    all_observations: list[object] = []
    reason_counts: dict[str, int] = {}
    for profile_name, nominal_delay_ms in PROFILE_PROBE_DELAYS_MS:
        profile_report, profile_observations, profile_reason_counts = await _run_profile_probe(
            profile_name=profile_name,
            nominal_delay_ms=nominal_delay_ms,
            samples=samples,
            timeout_samples=timeout_samples,
            budget_ms=budget_ms,
            timeout_ms=timeout_ms,
            fail_mode=fail_mode,
        )
        profile_reports.append(profile_report)
        all_observations.extend(profile_observations)
        reason_counts = _merge_reason_counts(reason_counts, profile_reason_counts)

    return {
        "summary": _summary_from_observations(
            observations=all_observations,
            budget_ms=budget_ms,
            timeout_ms=timeout_ms,
            fail_mode=fail_mode,
        ),
        "profiles": profile_reports,
        "reason_code_counts": reason_counts,
    }


def _load_thresholds(path: str) -> dict[str, object]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    global_max_p95 = float(payload.get("max_p95_ingress_latency_ms", 250.0))
    global_max_timeout_rate = float(payload.get("max_timeout_rate", 0.2))
    raw_profiles = payload.get("profiles", {})
    profile_thresholds: dict[str, dict[str, float]] = {}
    if isinstance(raw_profiles, dict):
        for profile_name, profile_payload in raw_profiles.items():
            if not isinstance(profile_payload, dict):
                continue
            normalized_profile = _normalize_profile_name(profile_name)
            profile_thresholds[normalized_profile] = {
                "max_p95_ingress_latency_ms": float(
                    profile_payload.get("max_p95_ingress_latency_ms", global_max_p95)
                ),
                "max_timeout_rate": float(profile_payload.get("max_timeout_rate", global_max_timeout_rate)),
            }
    return {
        "max_p95_ingress_latency_ms": global_max_p95,
        "max_timeout_rate": global_max_timeout_rate,
        "profiles": profile_thresholds,
    }


def _threshold_for_profile(thresholds: dict[str, object], profile_name: str) -> dict[str, float]:
    max_p95 = float(thresholds.get("max_p95_ingress_latency_ms", 250.0))
    max_timeout_rate = float(thresholds.get("max_timeout_rate", 0.2))
    profiles = thresholds.get("profiles", {})
    if isinstance(profiles, dict):
        profile_threshold = profiles.get(_normalize_profile_name(profile_name))
        if isinstance(profile_threshold, dict):
            max_p95 = float(profile_threshold.get("max_p95_ingress_latency_ms", max_p95))
            max_timeout_rate = float(profile_threshold.get("max_timeout_rate", max_timeout_rate))
    return {
        "max_p95_ingress_latency_ms": max_p95,
        "max_timeout_rate": max_timeout_rate,
    }


def _enforce_thresholds(report: dict[str, object], thresholds: dict[str, object]) -> list[str]:
    failed_checks: list[str] = []
    summary = report.get("summary", {})
    if isinstance(summary, dict):
        if float(summary.get("p95_ingress_latency_ms", 0.0)) > float(thresholds["max_p95_ingress_latency_ms"]):
            failed_checks.append("overall:p95_ingress_latency_ms")
        if float(summary.get("timeout_rate", 0.0)) > float(thresholds["max_timeout_rate"]):
            failed_checks.append("overall:timeout_rate")

    profile_reports = report.get("profiles", [])
    if not isinstance(profile_reports, list):
        return failed_checks
    for profile_report in profile_reports:
        if not isinstance(profile_report, dict):
            continue
        profile_name = _normalize_profile_name(str(profile_report.get("profile", "baseline")))
        profile_summary = profile_report.get("summary", {})
        if not isinstance(profile_summary, dict):
            continue
        profile_threshold = _threshold_for_profile(thresholds, profile_name)
        if float(profile_summary.get("p95_ingress_latency_ms", 0.0)) > profile_threshold["max_p95_ingress_latency_ms"]:
            failed_checks.append(f"{profile_name}:p95_ingress_latency_ms")
        if float(profile_summary.get("timeout_rate", 0.0)) > profile_threshold["max_timeout_rate"]:
            failed_checks.append(f"{profile_name}:timeout_rate")
    return failed_checks


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingress latency/timeout budget probe.")
    parser.add_argument("--samples", type=int, default=30, help="Number of non-timeout baseline samples.")
    parser.add_argument("--timeout-samples", type=int, default=3, help="Number of forced-timeout samples.")
    parser.add_argument("--budget-ms", type=int, default=75, help="Latency budget threshold used in probe.")
    parser.add_argument("--timeout-ms", type=int, default=30, help="Ingress timeout used in probe.")
    parser.add_argument("--fail-mode", default="fail_closed", choices=["fail_closed", "fail_open"])
    parser.add_argument("--json-out", default="", help="Optional output file for structured report.")
    parser.add_argument("--enforce", action="store_true", help="Fail when SLO thresholds are breached.")
    parser.add_argument(
        "--thresholds-json",
        default="configs/release/ingress_budget_thresholds.json",
        help="JSON file with max_p95_ingress_latency_ms and max_timeout_rate.",
    )
    args = parser.parse_args()

    report = asyncio.run(
        _run_probe(
            samples=max(args.samples, 1),
            timeout_samples=max(args.timeout_samples, 0),
            budget_ms=max(args.budget_ms, 1),
            timeout_ms=max(args.timeout_ms, 1),
            fail_mode=str(args.fail_mode).strip().lower(),
        )
    )
    summary = report["summary"]
    print("scope,profile,samples,p95_ingress_latency_ms,timeout_total,timeout_rate,budget_ms,timeout_ms,fail_mode")
    print(
        f"overall,all,{summary['samples']},{summary['p95_ingress_latency_ms']},{summary['timeout_total']},"
        f"{summary['timeout_rate']},{summary['budget_ms']},{summary['timeout_ms']},{summary['fail_mode']}"
    )
    for profile_report in report.get("profiles", []):
        profile_summary = profile_report.get("summary", {})
        profile_name = profile_report.get("profile", "baseline")
        print(
            f"profile,{profile_name},{profile_summary.get('samples', 0)},"
            f"{profile_summary.get('p95_ingress_latency_ms', 0.0)},"
            f"{profile_summary.get('timeout_total', 0)},"
            f"{profile_summary.get('timeout_rate', 0.0)},"
            f"{profile_summary.get('budget_ms', summary['budget_ms'])},"
            f"{profile_summary.get('timeout_ms', summary['timeout_ms'])},"
            f"{profile_summary.get('fail_mode', summary['fail_mode'])}"
        )

    if args.json_out:
        out_path = Path(args.json_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    if not args.enforce:
        return 0

    thresholds = _load_thresholds(args.thresholds_json)
    failed_checks = _enforce_thresholds(report, thresholds)
    if failed_checks:
        print(f"INGRESS_BUDGET_ENFORCEMENT_FAILED: {', '.join(failed_checks)}")
        return 1
    print("INGRESS_BUDGET_ENFORCEMENT_PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
