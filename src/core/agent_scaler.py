"""
File: agent_scaler.py
Path: src/core/agent_scaler.py
Role: Computes autoscaling and backpressure decisions for background execution.
Used By:
 - src/core/background_runtime.py
Depends On:
 - dataclasses
 - math
Notes:
 - This module is policy-only; it does not directly mutate worker pool state.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil


@dataclass(slots=True)
class AgentScalerConfig:
    enabled: bool = False
    min_concurrency: int = 1
    max_concurrency: int = 8
    scale_up_backlog_threshold: int = 2
    scale_up_step: int = 1
    scale_up_cooldown_evaluations: int = 0
    scale_up_hysteresis_backlog_delta: int = 0
    backpressure_backlog_threshold: int = 8
    backpressure_active_ratio_threshold: float = 1.0


@dataclass(slots=True)
class AgentScalerDecision:
    target_concurrency: int
    scale_up: bool
    backpressure: bool
    reason_code: str
    diagnostics: dict[str, int | float | bool | str]


class AgentScaler:
    def __init__(self, config: AgentScalerConfig) -> None:
        self._config = config
        self._cooldown_remaining = 0
        self._last_scale_up_target = 0
        if config.min_concurrency < 1:
            raise ValueError("min_concurrency must be >= 1")
        if config.max_concurrency < config.min_concurrency:
            raise ValueError("max_concurrency must be >= min_concurrency")
        if config.scale_up_backlog_threshold < 0:
            raise ValueError("scale_up_backlog_threshold must be >= 0")
        if config.scale_up_step < 1:
            raise ValueError("scale_up_step must be >= 1")
        if config.scale_up_cooldown_evaluations < 0:
            raise ValueError("scale_up_cooldown_evaluations must be >= 0")
        if config.scale_up_hysteresis_backlog_delta < 0:
            raise ValueError("scale_up_hysteresis_backlog_delta must be >= 0")
        if config.backpressure_backlog_threshold < 1:
            raise ValueError("backpressure_backlog_threshold must be >= 1")
        if config.backpressure_active_ratio_threshold <= 0:
            raise ValueError("backpressure_active_ratio_threshold must be > 0")

    def evaluate(
        self,
        *,
        active_jobs: int,
        pending_jobs: int,
        current_concurrency: int,
    ) -> AgentScalerDecision:
        if not self._config.enabled:
            return AgentScalerDecision(
                target_concurrency=max(current_concurrency, self._config.min_concurrency),
                scale_up=False,
                backpressure=False,
                reason_code="SCALER_DISABLED",
                diagnostics={
                    "effective_scale_up_threshold": self._config.scale_up_backlog_threshold,
                    "active_threshold": 0,
                    "cooldown_remaining": self._cooldown_remaining,
                },
            )
        normalized = max(current_concurrency, self._config.min_concurrency)
        target = normalized
        scale_up = False
        reason_code = "OK"
        active_threshold = ceil(normalized * self._config.backpressure_active_ratio_threshold)
        effective_scale_up_threshold = self._config.scale_up_backlog_threshold
        if (
            self._config.scale_up_hysteresis_backlog_delta > 0
            and self._last_scale_up_target >= normalized
            and normalized > self._config.min_concurrency
        ):
            effective_scale_up_threshold += self._config.scale_up_hysteresis_backlog_delta
        cooldown_applied = False
        if self._cooldown_remaining > 0:
            cooldown_applied = True
            self._cooldown_remaining -= 1

        if (
            pending_jobs >= effective_scale_up_threshold
            and normalized < self._config.max_concurrency
            and not cooldown_applied
        ):
            target = min(self._config.max_concurrency, normalized + self._config.scale_up_step)
            scale_up = target > normalized
            if scale_up:
                self._last_scale_up_target = target
                self._cooldown_remaining = self._config.scale_up_cooldown_evaluations
        elif cooldown_applied and pending_jobs >= effective_scale_up_threshold and normalized < self._config.max_concurrency:
            reason_code = "SCALER_COOLDOWN_ACTIVE"

        backpressure = pending_jobs >= self._config.backpressure_backlog_threshold and active_jobs >= active_threshold
        if backpressure:
            reason_code = "BACKPRESSURE_THRESHOLD_EXCEEDED"
        elif scale_up:
            reason_code = "SCALE_UP_THRESHOLD_REACHED"
        return AgentScalerDecision(
            target_concurrency=target,
            scale_up=scale_up,
            backpressure=backpressure,
            reason_code=reason_code,
            diagnostics={
                "effective_scale_up_threshold": effective_scale_up_threshold,
                "active_threshold": active_threshold,
                "cooldown_remaining": self._cooldown_remaining,
                "cooldown_applied": cooldown_applied,
            },
        )
