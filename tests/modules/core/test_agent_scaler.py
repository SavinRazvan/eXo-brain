"""
File: test_agent_scaler.py
Path: tests/modules/core/test_agent_scaler.py
Role: Unit coverage for autoscaling and backpressure policy decisions.
Used By:
 - pytest
Depends On:
 - src/core/agent_scaler.py
Notes:
 - Verifies threshold-driven decisions remain deterministic.
"""

from __future__ import annotations

from src.core.agent_scaler import AgentScaler, AgentScalerConfig


def test_agent_scaler_scales_up_when_backlog_threshold_is_reached() -> None:
    scaler = AgentScaler(
        AgentScalerConfig(
            enabled=True,
            min_concurrency=1,
            max_concurrency=4,
            scale_up_backlog_threshold=2,
            scale_up_step=1,
            backpressure_backlog_threshold=8,
            backpressure_active_ratio_threshold=1.0,
        )
    )

    decision = scaler.evaluate(active_jobs=1, pending_jobs=2, current_concurrency=1)

    assert decision.scale_up is True
    assert decision.target_concurrency == 2
    assert decision.backpressure is False
    assert decision.reason_code == "SCALE_UP_THRESHOLD_REACHED"


def test_agent_scaler_applies_backpressure_when_thresholds_exceeded() -> None:
    scaler = AgentScaler(
        AgentScalerConfig(
            enabled=True,
            min_concurrency=1,
            max_concurrency=4,
            scale_up_backlog_threshold=2,
            scale_up_step=1,
            backpressure_backlog_threshold=3,
            backpressure_active_ratio_threshold=1.0,
        )
    )

    decision = scaler.evaluate(active_jobs=2, pending_jobs=3, current_concurrency=2)

    assert decision.backpressure is True
    assert decision.reason_code == "BACKPRESSURE_THRESHOLD_EXCEEDED"


def test_agent_scaler_disabled_returns_noop_decision() -> None:
    scaler = AgentScaler(AgentScalerConfig(enabled=False))

    decision = scaler.evaluate(active_jobs=100, pending_jobs=100, current_concurrency=2)

    assert decision.scale_up is False
    assert decision.backpressure is False
    assert decision.target_concurrency == 2
    assert decision.reason_code == "SCALER_DISABLED"
