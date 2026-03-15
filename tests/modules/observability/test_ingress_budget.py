"""
File: test_ingress_budget.py
Path: tests/modules/observability/test_ingress_budget.py
Role: Unit tests for ingress governance budget timing and fail-safe helpers.
Used By:
 - pytest
Depends On:
 - src/observability/ingress_budget.py
 - src/policies/ingress_gates.py
Notes:
 - Covers p95 calculation, timeout fail-safe behavior, and recorder summaries.
"""

from __future__ import annotations

import asyncio

from src.observability.ingress_budget import (
    IngressBudgetConfig,
    IngressBudgetObservation,
    IngressBudgetRecorder,
    evaluate_with_budget,
    percentile,
)
from src.policies.ingress_gates import IngressDecision
from src.schemas.tool_io import PolicyAction


def test_percentile_returns_expected_p95() -> None:
    values = [1.0, 4.0, 2.0, 3.0, 5.0]
    assert percentile(values, 0.95) == 4.0


def test_budget_recorder_summary_reports_p95_and_timeout_rate() -> None:
    recorder = IngressBudgetRecorder()
    recorder.observe(
        tenant_id="t1",
        observation=IngressBudgetObservation(
            latency_ms=10.0,
            budget_ms=20,
            timeout_ms=15,
            timeout_fail_mode="fail_closed",
            timed_out=False,
            budget_exceeded=False,
            reason_code="INGRESS_ALLOW_DEFAULT",
            decision="allow",
            ingress_profile="baseline",
        ),
    )
    recorder.observe(
        tenant_id="t1",
        observation=IngressBudgetObservation(
            latency_ms=30.0,
            budget_ms=20,
            timeout_ms=15,
            timeout_fail_mode="fail_closed",
            timed_out=True,
            budget_exceeded=True,
            reason_code="INGRESS_GATE_TIMEOUT_FAIL_CLOSED",
            decision="deny",
            ingress_profile="strict",
        ),
    )
    summary = recorder.summary(tenant_id="t1")
    assert summary["samples"] == 2
    assert summary["timeout_total"] == 1
    assert summary["timeout_rate"] == 0.5
    assert summary["budget_exceeded_total"] == 1
    profiles = summary["profiles"]
    assert profiles["baseline"]["samples"] == 1
    assert profiles["strict"]["samples"] == 1


def test_ingress_budget_observation_payload_normalizes_profile_name() -> None:
    observation = IngressBudgetObservation(
        latency_ms=2.0,
        budget_ms=20,
        timeout_ms=15,
        timeout_fail_mode="fail_closed",
        timed_out=False,
        budget_exceeded=False,
        reason_code="INGRESS_ALLOW_DEFAULT",
        decision="allow",
        ingress_profile=" STRICT ",
    )
    payload = observation.to_payload()
    assert payload["ingress_profile"] == "strict"


def test_evaluate_with_budget_returns_fail_closed_timeout_decision() -> None:
    async def _slow_decision() -> IngressDecision:
        await asyncio.sleep(0.02)
        return IngressDecision(
            schema_version="1.0",
            decision=PolicyAction.ALLOW,
            reason_code="INGRESS_ALLOW_DEFAULT",
            message="allowed",
            gate_id="gate",
            gate_version="1.0.0",
        )

    decision, observation = asyncio.run(
        evaluate_with_budget(
            evaluate=_slow_decision,
            config=IngressBudgetConfig(latency_budget_ms=5, timeout_ms=5, timeout_fail_mode="fail_closed"),
        )
    )
    assert decision.decision == PolicyAction.DENY
    assert decision.reason_code == "INGRESS_GATE_TIMEOUT_FAIL_CLOSED"
    assert observation.timed_out is True


def test_evaluate_with_budget_returns_fail_open_timeout_decision() -> None:
    async def _slow_decision() -> IngressDecision:
        await asyncio.sleep(0.02)
        return IngressDecision(
            schema_version="1.0",
            decision=PolicyAction.ALLOW,
            reason_code="INGRESS_ALLOW_DEFAULT",
            message="allowed",
            gate_id="gate",
            gate_version="1.0.0",
        )

    decision, observation = asyncio.run(
        evaluate_with_budget(
            evaluate=_slow_decision,
            config=IngressBudgetConfig(latency_budget_ms=5, timeout_ms=5, timeout_fail_mode="fail_open"),
        )
    )
    assert decision.decision == PolicyAction.ALLOW
    assert decision.reason_code == "INGRESS_GATE_TIMEOUT_FAIL_OPEN"
    assert observation.timed_out is True


def test_evaluate_with_budget_captures_profile_name() -> None:
    async def _fast_decision() -> IngressDecision:
        return IngressDecision(
            schema_version="1.0",
            decision=PolicyAction.ALLOW,
            reason_code="INGRESS_ALLOW_DEFAULT",
            message="allowed",
            gate_id="gate",
            gate_version="1.0.0",
        )

    _decision, observation = asyncio.run(
        evaluate_with_budget(
            evaluate=_fast_decision,
            config=IngressBudgetConfig(latency_budget_ms=20, timeout_ms=20, timeout_fail_mode="fail_closed"),
            profile_name="hardened",
        )
    )
    assert observation.ingress_profile == "hardened"
