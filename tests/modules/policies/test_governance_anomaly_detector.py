"""
File: test_governance_anomaly_detector.py
Path: tests/modules/policies/test_governance_anomaly_detector.py
Role: Unit tests for deterministic BYOC governance anomaly detection logic.
Used By:
 - pytest
Depends On:
 - src/policies/governance_anomaly_detector.py
Notes:
 - Detector is advisory-only and should never mutate runtime state.
"""

from __future__ import annotations

from src.policies.governance_anomaly_detector import (
    GovernanceAnomalyThresholds,
    detect_governance_anomalies,
)


def test_detect_governance_anomalies_emits_spike_and_dominance_findings() -> None:
    thresholds = GovernanceAnomalyThresholds(
        cost_utilization_threshold=0.8,
        rejection_rate_threshold=0.25,
        reason_share_threshold=0.6,
        min_submit_attempts=5,
        min_rejection_count=3,
    )
    anomalies = detect_governance_anomalies(
        cost_utilization_ratio=0.91,
        rejection_rate=0.40,
        submit_attempts_total=10,
        rejected_results_total=4,
        rejection_reason_counts={"BYOC_LEASE_INVALID_OR_EXPIRED": 3, "OTHER": 1},
        thresholds=thresholds,
    )
    codes = [item.code for item in anomalies]
    assert codes == [
        "BYOC_COST_UTILIZATION_SPIKE",
        "BYOC_REJECTION_RATE_SPIKE",
        "BYOC_REJECTION_REASON_DOMINANCE",
    ]
    assert anomalies[-1].reason_code == "BYOC_LEASE_INVALID_OR_EXPIRED"


def test_detect_governance_anomalies_returns_empty_below_min_submit_attempts() -> None:
    thresholds = GovernanceAnomalyThresholds(min_submit_attempts=5)
    anomalies = detect_governance_anomalies(
        cost_utilization_ratio=1.0,
        rejection_rate=1.0,
        submit_attempts_total=4,
        rejected_results_total=4,
        rejection_reason_counts={"X": 4},
        thresholds=thresholds,
    )
    assert anomalies == []
