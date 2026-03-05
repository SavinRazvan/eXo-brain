"""
File: governance_anomaly_detector.py
Path: src/policies/governance_anomaly_detector.py
Role: Deterministic advisory anomaly detection for tenant governance metrics.
Used By:
 - src/api/routers/runtime_control.py
Depends On:
 - dataclasses
Notes:
 - Advisory only: findings are for triage and do not block runtime admission.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GovernanceAnomalyThresholds:
    cost_utilization_threshold: float = 0.9
    rejection_rate_threshold: float = 0.2
    reason_share_threshold: float = 0.6
    min_submit_attempts: int = 5
    min_rejection_count: int = 3


@dataclass(frozen=True)
class GovernanceAnomaly:
    code: str
    severity: str
    message: str
    value: float
    threshold: float
    reason_code: str = ""


def detect_governance_anomalies(
    *,
    cost_utilization_ratio: float,
    rejection_rate: float,
    submit_attempts_total: int,
    rejected_results_total: int,
    rejection_reason_counts: dict[str, int],
    thresholds: GovernanceAnomalyThresholds,
) -> list[GovernanceAnomaly]:
    anomalies: list[GovernanceAnomaly] = []
    min_attempts = max(int(thresholds.min_submit_attempts), 0)
    if int(submit_attempts_total) < min_attempts:
        return anomalies

    if float(cost_utilization_ratio) >= float(thresholds.cost_utilization_threshold):
        anomalies.append(
            GovernanceAnomaly(
                code="BYOC_COST_UTILIZATION_SPIKE",
                severity="warning",
                message="Tenant cost utilization exceeded advisory threshold.",
                value=float(cost_utilization_ratio),
                threshold=float(thresholds.cost_utilization_threshold),
            )
        )
    if float(rejection_rate) >= float(thresholds.rejection_rate_threshold):
        anomalies.append(
            GovernanceAnomaly(
                code="BYOC_REJECTION_RATE_SPIKE",
                severity="warning",
                message="Tenant rejection rate exceeded advisory threshold.",
                value=float(rejection_rate),
                threshold=float(thresholds.rejection_rate_threshold),
            )
        )

    total_rejections = max(int(rejected_results_total), 0)
    min_rejections = max(int(thresholds.min_rejection_count), 0)
    if total_rejections < min_rejections or total_rejections <= 0:
        return anomalies

    sorted_reasons = sorted(
        ((str(reason), int(count)) for reason, count in rejection_reason_counts.items()),
        key=lambda item: (-item[1], item[0]),
    )
    for reason_code, count in sorted_reasons:
        if count < min_rejections:
            continue
        reason_share = float(count / total_rejections)
        if reason_share >= float(thresholds.reason_share_threshold):
            anomalies.append(
                GovernanceAnomaly(
                    code="BYOC_REJECTION_REASON_DOMINANCE",
                    severity="warning",
                    message="A single rejection reason dominates tenant failures.",
                    value=reason_share,
                    threshold=float(thresholds.reason_share_threshold),
                    reason_code=reason_code,
                )
            )
    return anomalies
