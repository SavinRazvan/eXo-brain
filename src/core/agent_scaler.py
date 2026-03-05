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
    backpressure_backlog_threshold: int = 8
    backpressure_active_ratio_threshold: float = 1.0


@dataclass(slots=True)
class AgentScalerDecision:
    target_concurrency: int
    scale_up: bool
    backpressure: bool
    reason_code: str


class AgentScaler:
    def __init__(self, config: AgentScalerConfig) -> None:
        self._config = config
        if config.min_concurrency < 1:
            raise ValueError("min_concurrency must be >= 1")
        if config.max_concurrency < config.min_concurrency:
            raise ValueError("max_concurrency must be >= min_concurrency")
        if config.scale_up_backlog_threshold < 0:
            raise ValueError("scale_up_backlog_threshold must be >= 0")
        if config.scale_up_step < 1:
            raise ValueError("scale_up_step must be >= 1")
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
            )
        normalized = max(current_concurrency, self._config.min_concurrency)
        target = normalized
        scale_up = False

        if pending_jobs >= self._config.scale_up_backlog_threshold and normalized < self._config.max_concurrency:
            target = min(self._config.max_concurrency, normalized + self._config.scale_up_step)
            scale_up = target > normalized

        active_threshold = ceil(normalized * self._config.backpressure_active_ratio_threshold)
        backpressure = pending_jobs >= self._config.backpressure_backlog_threshold and active_jobs >= active_threshold
        reason_code = "OK"
        if backpressure:
            reason_code = "BACKPRESSURE_THRESHOLD_EXCEEDED"
        elif scale_up:
            reason_code = "SCALE_UP_THRESHOLD_REACHED"
        return AgentScalerDecision(
            target_concurrency=target,
            scale_up=scale_up,
            backpressure=backpressure,
            reason_code=reason_code,
        )
