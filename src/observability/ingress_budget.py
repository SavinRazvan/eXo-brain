"""
File: ingress_budget.py
Path: src/observability/ingress_budget.py
Role: Ingress governance latency budget helpers and timeout fail-safe controls.
Used By:
 - src/api/routers/turns.py
 - scripts/perf/ingress_budget_report.py
Depends On:
 - src/policies/ingress_gates.py
Notes:
 - Budget evaluation is deterministic and fail-safe with explicit reason codes.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from threading import Lock
from time import perf_counter
from typing import Any, Awaitable, Callable

from src.policies.ingress_gates import IngressDecision
from src.schemas.tool_io import PolicyAction


@dataclass(slots=True)
class IngressBudgetConfig:
    latency_budget_ms: int = 75
    timeout_ms: int = 150
    timeout_fail_mode: str = "fail_closed"

    def normalized_fail_mode(self) -> str:
        value = str(self.timeout_fail_mode).strip().lower()
        if value == "fail_open":
            return "fail_open"
        return "fail_closed"


@dataclass(slots=True)
class IngressBudgetObservation:
    latency_ms: float
    budget_ms: int
    timeout_ms: int
    timeout_fail_mode: str
    timed_out: bool
    budget_exceeded: bool
    reason_code: str
    decision: str

    def to_payload(self) -> dict[str, object]:
        return {
            "latency_ms": round(float(self.latency_ms), 3),
            "budget_ms": int(self.budget_ms),
            "timeout_ms": int(self.timeout_ms),
            "timeout_fail_mode": self.timeout_fail_mode,
            "timed_out": self.timed_out,
            "budget_exceeded": self.budget_exceeded,
            "reason_code": self.reason_code,
            "decision": self.decision,
        }


class IngressBudgetRecorder:
    def __init__(self) -> None:
        self._lock = Lock()
        self._samples_by_tenant: dict[str, list[IngressBudgetObservation]] = {}

    def observe(self, *, tenant_id: str, observation: IngressBudgetObservation) -> None:
        with self._lock:
            samples = self._samples_by_tenant.setdefault(str(tenant_id), [])
            samples.append(observation)

    def summary(self, *, tenant_id: str) -> dict[str, object]:
        with self._lock:
            samples = list(self._samples_by_tenant.get(str(tenant_id), []))
        if not samples:
            return {
                "samples": 0,
                "p95_latency_ms": 0.0,
                "timeout_total": 0,
                "timeout_rate": 0.0,
                "budget_exceeded_total": 0,
            }
        latencies = [sample.latency_ms for sample in samples]
        timeout_total = sum(1 for sample in samples if sample.timed_out)
        budget_exceeded_total = sum(1 for sample in samples if sample.budget_exceeded)
        return {
            "samples": len(samples),
            "p95_latency_ms": round(percentile(latencies, 0.95), 3),
            "timeout_total": timeout_total,
            "timeout_rate": round(float(timeout_total) / float(len(samples)), 6),
            "budget_exceeded_total": budget_exceeded_total,
        }


def percentile(values: list[float], ratio: float) -> float:
    if not values:
        return 0.0
    bounded_ratio = min(max(float(ratio), 0.0), 1.0)
    ordered = sorted(float(value) for value in values)
    index = max(int(len(ordered) * bounded_ratio) - 1, 0)
    return ordered[index]


def timeout_decision(*, fail_mode: str) -> IngressDecision:
    normalized = str(fail_mode).strip().lower()
    if normalized == "fail_open":
        return IngressDecision(
            schema_version="1.0",
            decision=PolicyAction.ALLOW,
            reason_code="INGRESS_GATE_TIMEOUT_FAIL_OPEN",
            message="Ingress gate evaluation timed out and fail-open mode allowed this turn.",
            gate_id="ingress-budget-controller",
            gate_version="1.0.0",
        )
    return IngressDecision(
        schema_version="1.0",
        decision=PolicyAction.DENY,
        reason_code="INGRESS_GATE_TIMEOUT_FAIL_CLOSED",
        message="Ingress gate evaluation timed out and fail-closed mode denied this turn.",
        gate_id="ingress-budget-controller",
        gate_version="1.0.0",
    )


async def evaluate_with_budget(
    *,
    evaluate: Callable[[], Awaitable[IngressDecision]],
    config: IngressBudgetConfig,
) -> tuple[IngressDecision, IngressBudgetObservation]:
    timeout_ms = max(int(config.timeout_ms), 1)
    budget_ms = max(int(config.latency_budget_ms), 1)
    fail_mode = config.normalized_fail_mode()
    timed_out = False
    started_at = perf_counter()
    try:
        decision = await asyncio.wait_for(evaluate(), timeout=float(timeout_ms) / 1000.0)
    except asyncio.TimeoutError:
        timed_out = True
        decision = timeout_decision(fail_mode=fail_mode)
    latency_ms = (perf_counter() - started_at) * 1000.0
    observation = IngressBudgetObservation(
        latency_ms=latency_ms,
        budget_ms=budget_ms,
        timeout_ms=timeout_ms,
        timeout_fail_mode=fail_mode,
        timed_out=timed_out,
        budget_exceeded=latency_ms > float(budget_ms),
        reason_code=decision.reason_code,
        decision=decision.decision.value,
    )
    return decision, observation


def budget_config_from_policy_settings(policy_settings: Any) -> IngressBudgetConfig:
    latency_budget_ms = int(getattr(policy_settings, "ingress_latency_budget_ms", 75))
    timeout_ms = int(getattr(policy_settings, "ingress_timeout_ms", 150))
    timeout_fail_mode = str(getattr(policy_settings, "ingress_timeout_fail_mode", "fail_closed")).strip().lower()
    return IngressBudgetConfig(
        latency_budget_ms=max(latency_budget_ms, 1),
        timeout_ms=max(timeout_ms, 1),
        timeout_fail_mode=timeout_fail_mode or "fail_closed",
    )
