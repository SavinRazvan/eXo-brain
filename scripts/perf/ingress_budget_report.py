"""
File: ingress_budget_report.py
Path: scripts/perf/ingress_budget_report.py
Role: Deterministic ingress budget probe that reports p95 latency and timeout fail-safe outcomes.
Used By:
 - scripts/release/verify_gates.py
Depends On:
 - src/observability/ingress_budget.py
 - src/policies/ingress_gates.py
Notes:
 - This is a local simulation harness and not a full transport benchmark.
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


async def _run_probe(
    *,
    samples: int,
    timeout_samples: int,
    budget_ms: int,
    timeout_ms: int,
    fail_mode: str,
) -> dict[str, object]:
    observations = []
    for _ in range(max(samples, 1)):
        decision, observation = await evaluate_with_budget(
            evaluate=_fast_eval,
            config=IngressBudgetConfig(
                latency_budget_ms=budget_ms,
                timeout_ms=timeout_ms,
                timeout_fail_mode=fail_mode,
            ),
        )
        observations.append((decision, observation))

    for _ in range(max(timeout_samples, 0)):
        decision, observation = await evaluate_with_budget(
            evaluate=lambda: _slow_eval(max(timeout_ms + 10, 20)),
            config=IngressBudgetConfig(
                latency_budget_ms=budget_ms,
                timeout_ms=timeout_ms,
                timeout_fail_mode=fail_mode,
            ),
        )
        observations.append((decision, observation))

    latencies = [item[1].latency_ms for item in observations]
    timed_out = [item for item in observations if item[1].timed_out]
    reason_counts: dict[str, int] = {}
    for decision, _observation in observations:
        reason_counts[decision.reason_code] = reason_counts.get(decision.reason_code, 0) + 1

    total = len(observations)
    timeout_total = len(timed_out)
    return {
        "summary": {
            "samples": total,
            "p95_ingress_latency_ms": round(percentile(latencies, 0.95), 3),
            "timeout_total": timeout_total,
            "timeout_rate": round(float(timeout_total) / float(total), 6) if total > 0 else 0.0,
            "budget_ms": budget_ms,
            "timeout_ms": timeout_ms,
            "fail_mode": fail_mode,
        },
        "reason_code_counts": reason_counts,
    }


def _load_thresholds(path: str) -> dict[str, float]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return {
        "max_p95_ingress_latency_ms": float(payload.get("max_p95_ingress_latency_ms", 250.0)),
        "max_timeout_rate": float(payload.get("max_timeout_rate", 0.2)),
    }


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
    print("samples,p95_ingress_latency_ms,timeout_total,timeout_rate,budget_ms,timeout_ms,fail_mode")
    print(
        f"{summary['samples']},{summary['p95_ingress_latency_ms']},{summary['timeout_total']},"
        f"{summary['timeout_rate']},{summary['budget_ms']},{summary['timeout_ms']},{summary['fail_mode']}"
    )

    if args.json_out:
        out_path = Path(args.json_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    if not args.enforce:
        return 0

    thresholds = _load_thresholds(args.thresholds_json)
    failed_checks: list[str] = []
    if float(summary["p95_ingress_latency_ms"]) > thresholds["max_p95_ingress_latency_ms"]:
        failed_checks.append("p95_ingress_latency_ms")
    if float(summary["timeout_rate"]) > thresholds["max_timeout_rate"]:
        failed_checks.append("timeout_rate")
    if failed_checks:
        print(f"INGRESS_BUDGET_ENFORCEMENT_FAILED: {', '.join(failed_checks)}")
        return 1
    print("INGRESS_BUDGET_ENFORCEMENT_PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
