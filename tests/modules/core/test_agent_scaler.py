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

import pytest

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
    assert decision.diagnostics["effective_scale_up_threshold"] == 2


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
    assert decision.diagnostics["cooldown_remaining"] == 0


def test_agent_scaler_enforces_cooldown_between_scale_up_events() -> None:
    scaler = AgentScaler(
        AgentScalerConfig(
            enabled=True,
            min_concurrency=1,
            max_concurrency=4,
            scale_up_backlog_threshold=1,
            scale_up_step=1,
            scale_up_cooldown_evaluations=2,
            backpressure_backlog_threshold=50,
        )
    )

    first = scaler.evaluate(active_jobs=1, pending_jobs=2, current_concurrency=1)
    second = scaler.evaluate(active_jobs=1, pending_jobs=2, current_concurrency=2)
    third = scaler.evaluate(active_jobs=1, pending_jobs=2, current_concurrency=2)
    fourth = scaler.evaluate(active_jobs=1, pending_jobs=2, current_concurrency=2)

    assert first.scale_up is True
    assert second.scale_up is False
    assert second.reason_code == "SCALER_COOLDOWN_ACTIVE"
    assert third.scale_up is False
    assert third.reason_code == "SCALER_COOLDOWN_ACTIVE"
    assert fourth.scale_up is True


def test_agent_scaler_init_validates_configuration_fields() -> None:
    with pytest.raises(ValueError, match="min_concurrency"):
        AgentScaler(AgentScalerConfig(min_concurrency=0))
    with pytest.raises(ValueError, match="max_concurrency"):
        AgentScaler(AgentScalerConfig(min_concurrency=2, max_concurrency=1))
    with pytest.raises(ValueError, match="scale_up_backlog_threshold"):
        AgentScaler(AgentScalerConfig(scale_up_backlog_threshold=-1))
    with pytest.raises(ValueError, match="scale_up_step"):
        AgentScaler(AgentScalerConfig(scale_up_step=0))
    with pytest.raises(ValueError, match="scale_up_cooldown_evaluations"):
        AgentScaler(AgentScalerConfig(scale_up_cooldown_evaluations=-1))
    with pytest.raises(ValueError, match="scale_up_hysteresis_backlog_delta"):
        AgentScaler(AgentScalerConfig(scale_up_hysteresis_backlog_delta=-1))
    with pytest.raises(ValueError, match="backpressure_backlog_threshold"):
        AgentScaler(AgentScalerConfig(backpressure_backlog_threshold=0))
    with pytest.raises(ValueError, match="backpressure_active_ratio_threshold"):
        AgentScaler(AgentScalerConfig(backpressure_active_ratio_threshold=0))


def test_agent_scaler_hysteresis_requires_extra_backlog_after_scale_up() -> None:
    scaler = AgentScaler(
        AgentScalerConfig(
            enabled=True,
            min_concurrency=1,
            max_concurrency=4,
            scale_up_backlog_threshold=2,
            scale_up_step=1,
            scale_up_hysteresis_backlog_delta=2,
            backpressure_backlog_threshold=50,
        )
    )

    first = scaler.evaluate(active_jobs=1, pending_jobs=2, current_concurrency=1)
    second = scaler.evaluate(active_jobs=1, pending_jobs=3, current_concurrency=2)
    third = scaler.evaluate(active_jobs=1, pending_jobs=4, current_concurrency=2)

    assert first.scale_up is True
    assert second.scale_up is False
    assert second.diagnostics["effective_scale_up_threshold"] == 4
    assert third.scale_up is True
