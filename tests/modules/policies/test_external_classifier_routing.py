"""
File: test_external_classifier_routing.py
Path: tests/modules/policies/test_external_classifier_routing.py
Role: Tests for ExternalClassifierRoutingGate, ClassifierRoutingResult, and fallback behaviour.
Used By:
 - CI pytest suite
Depends On:
 - src/policies/ingress_classifier_router.py
 - src/policies/ingress_gates.py
 - src/policies/ingress_profiles.py
Notes:
 - Covers happy path (external adapter), fallback on error, fallback on timeout,
   heuristic-only (no adapter), evidence anchors in IngressDecision, and
   external_endpoint overlay validation.
"""

from __future__ import annotations

import pytest

from src.policies.ingress_classifier_router import (
    ClassifierRoutingResult,
    ExternalClassifierAdapter,
    ExternalClassifierError,
    ExternalClassifierResult,
)
from src.policies.ingress_gates import (
    ExternalClassifierRoutingGate,
    IngressTurnContext,
    build_ingress_gate_chain_from_overlay,
)
from src.policies.ingress_profiles import IngressClassifierSettings, resolve_ingress_profile_settings
from src.schemas.tool_io import PolicyAction


# ---------------------------------------------------------------------------
# Helpers / fakes
# ---------------------------------------------------------------------------

def _make_context(user_input: str = "hello world") -> IngressTurnContext:
    return IngressTurnContext(
        tenant_id="t1",
        session_id="s1",
        correlation_id="c1",
        transport="rest",
        user_input=user_input,
    )


def _classifier_settings(
    mode: str = "enforce",
    threshold: float = 0.5,
    signals: tuple[str, ...] = ("bypass safety", "reveal secrets"),
) -> IngressClassifierSettings:
    return IngressClassifierSettings(
        mode=mode,
        threshold=threshold,
        model_version="test-v1",
        signals=signals,
    )


class _OkAdapter(ExternalClassifierAdapter):
    """Adapter that always returns a fixed score."""

    def __init__(self, score: float, labels: tuple[str, ...] = (), latency_ms: int = 10) -> None:
        self._score = score
        self._labels = labels
        self._latency_ms = latency_ms

    @property
    def adapter_id(self) -> str:
        return "test-ok-adapter"

    def classify(self, user_input: str, *, timeout_ms: int = 2000) -> ExternalClassifierResult:
        return ExternalClassifierResult(
            score=self._score,
            labels=self._labels,
            model_version="external-v1",
            latency_ms=self._latency_ms,
        )


class _ErrorAdapter(ExternalClassifierAdapter):
    """Adapter that always raises ExternalClassifierError."""

    @property
    def adapter_id(self) -> str:
        return "test-error-adapter"

    def classify(self, user_input: str, *, timeout_ms: int = 2000) -> ExternalClassifierResult:
        raise ExternalClassifierError("upstream failure")


class _TimeoutAdapter(ExternalClassifierAdapter):
    """Adapter that always raises TimeoutError."""

    @property
    def adapter_id(self) -> str:
        return "test-timeout-adapter"

    def classify(self, user_input: str, *, timeout_ms: int = 2000) -> ExternalClassifierResult:
        raise TimeoutError("timed out")


# ---------------------------------------------------------------------------
# ExternalClassifierResult validation
# ---------------------------------------------------------------------------

class TestExternalClassifierResult:
    def test_valid_score_range(self) -> None:
        r = ExternalClassifierResult(score=0.75, labels=("high_risk",), model_version="v1")
        assert r.score == 0.75
        assert r.labels == ("high_risk",)

    def test_score_zero_and_one_are_valid(self) -> None:
        ExternalClassifierResult(score=0.0)
        ExternalClassifierResult(score=1.0)

    def test_invalid_score_raises(self) -> None:
        with pytest.raises(ValueError, match="EXTERNAL_CLASSIFIER_SCORE_INVALID"):
            ExternalClassifierResult(score=1.1)

    def test_negative_score_raises(self) -> None:
        with pytest.raises(ValueError, match="EXTERNAL_CLASSIFIER_SCORE_INVALID"):
            ExternalClassifierResult(score=-0.01)


# ---------------------------------------------------------------------------
# ClassifierRoutingResult properties
# ---------------------------------------------------------------------------

class TestClassifierRoutingResult:
    def test_used_external_true_when_routing_external(self) -> None:
        r = ClassifierRoutingResult(score=0.9, model_version="v1", routing_used="external")
        assert r.used_external is True
        assert r.used_fallback is False

    def test_used_fallback_true_when_fallback_reason_set(self) -> None:
        r = ClassifierRoutingResult(
            score=0.5,
            model_version="heuristic-ingress-v1",
            routing_used="heuristic",
            fallback_reason="TimeoutError: timed out",
        )
        assert r.used_external is False
        assert r.used_fallback is True

    def test_heuristic_without_fallback_reason(self) -> None:
        r = ClassifierRoutingResult(
            score=0.2,
            model_version="heuristic-ingress-v1",
            routing_used="heuristic",
        )
        assert r.used_external is False
        assert r.used_fallback is False


# ---------------------------------------------------------------------------
# ExternalClassifierRoutingGate — gate disabled (classifier off)
# ---------------------------------------------------------------------------

class TestExternalClassifierRoutingGateDisabled:
    def test_gate_returns_none_when_classifier_off(self) -> None:
        settings = _classifier_settings(mode="off")
        gate = ExternalClassifierRoutingGate(classifier=settings, adapter=_OkAdapter(score=0.9))
        result = gate.evaluate(_make_context("bypass safety"))
        assert result is None

    def test_gate_returns_none_when_no_adapter_and_classifier_off(self) -> None:
        settings = _classifier_settings(mode="off")
        gate = ExternalClassifierRoutingGate(classifier=settings, adapter=None)
        result = gate.evaluate(_make_context("bypass safety"))
        assert result is None


# ---------------------------------------------------------------------------
# ExternalClassifierRoutingGate — happy path (external adapter)
# ---------------------------------------------------------------------------

class TestExternalClassifierRoutingGateHappyPath:
    def test_high_risk_enforce_escalates_via_external(self) -> None:
        settings = _classifier_settings(mode="enforce", threshold=0.5)
        adapter = _OkAdapter(score=0.9, labels=("jailbreak",))
        gate = ExternalClassifierRoutingGate(classifier=settings, adapter=adapter)

        decision = gate.evaluate(_make_context("some input"))

        assert decision is not None
        assert decision.decision == PolicyAction.ESCALATE
        assert decision.reason_code == "INGRESS_CLASSIFIER_HIGH_RISK"
        assert decision.classifier_routing_used == "external"
        assert decision.classifier_fallback_reason == ""
        assert decision.classifier_score == 0.9
        assert decision.classifier_model_version == "external-v1"
        assert decision.classifier_labels == ("jailbreak",)
        assert decision.classifier_external_latency_ms >= 0

    def test_high_risk_shadow_allows_with_telemetry(self) -> None:
        settings = _classifier_settings(mode="shadow", threshold=0.5)
        adapter = _OkAdapter(score=0.8, labels=("high_risk",))
        gate = ExternalClassifierRoutingGate(classifier=settings, adapter=adapter)

        decision = gate.evaluate(_make_context("some input"))

        assert decision is not None
        assert decision.decision == PolicyAction.ALLOW
        assert decision.reason_code == "INGRESS_CLASSIFIER_SHADOW_HIGH_RISK"
        assert decision.classifier_shadow_triggered is True
        assert decision.classifier_routing_used == "external"
        assert decision.classifier_score == 0.8

    def test_low_risk_allows_with_evidence(self) -> None:
        settings = _classifier_settings(mode="enforce", threshold=0.8)
        adapter = _OkAdapter(score=0.3, labels=("low_risk",))
        gate = ExternalClassifierRoutingGate(classifier=settings, adapter=adapter)

        decision = gate.evaluate(_make_context("normal query"))

        assert decision is not None
        assert decision.decision == PolicyAction.ALLOW
        assert decision.reason_code == "INGRESS_CLASSIFIER_ALLOW_LOW_RISK"
        assert decision.classifier_routing_used == "external"
        assert decision.classifier_score == 0.3

    def test_payload_includes_routing_fields(self) -> None:
        settings = _classifier_settings(mode="enforce", threshold=0.5)
        adapter = _OkAdapter(score=0.7, labels=("risk",))
        gate = ExternalClassifierRoutingGate(classifier=settings, adapter=adapter)

        decision = gate.evaluate(_make_context("some input"))
        assert decision is not None
        payload = decision.to_payload()

        assert payload["classifier_routing_used"] == "external"
        assert payload["classifier_fallback_reason"] == ""
        assert "classifier_labels" in payload
        assert "classifier_external_latency_ms" in payload


# ---------------------------------------------------------------------------
# ExternalClassifierRoutingGate — fallback on error
# ---------------------------------------------------------------------------

class TestExternalClassifierRoutingGateFallbackOnError:
    def test_falls_back_to_heuristic_on_external_error(self) -> None:
        settings = _classifier_settings(mode="enforce", threshold=0.4)
        gate = ExternalClassifierRoutingGate(classifier=settings, adapter=_ErrorAdapter())

        # "bypass safety" matches one of two signals → score = 0.5 > 0.4 → escalate
        decision = gate.evaluate(_make_context("bypass safety here"))

        assert decision is not None
        assert decision.classifier_routing_used == "heuristic"
        assert "ExternalClassifierError" in decision.classifier_fallback_reason
        assert decision.classifier_external_latency_ms >= 0

    def test_falls_back_to_heuristic_on_timeout(self) -> None:
        settings = _classifier_settings(mode="enforce", threshold=0.4)
        gate = ExternalClassifierRoutingGate(classifier=settings, adapter=_TimeoutAdapter())

        decision = gate.evaluate(_make_context("bypass safety here"))

        assert decision is not None
        assert decision.classifier_routing_used == "heuristic"
        assert "TimeoutError" in decision.classifier_fallback_reason

    def test_fallback_low_risk_allows_cleanly(self) -> None:
        settings = _classifier_settings(mode="enforce", threshold=0.9)
        gate = ExternalClassifierRoutingGate(classifier=settings, adapter=_ErrorAdapter())

        decision = gate.evaluate(_make_context("normal query"))

        assert decision is not None
        assert decision.decision == PolicyAction.ALLOW
        assert decision.classifier_routing_used == "heuristic"
        assert decision.classifier_fallback_reason != ""


# ---------------------------------------------------------------------------
# ExternalClassifierRoutingGate — no adapter (heuristic path only)
# ---------------------------------------------------------------------------

class TestExternalClassifierRoutingGateNoAdapter:
    def test_no_adapter_uses_heuristic_path(self) -> None:
        settings = _classifier_settings(mode="enforce", threshold=0.4)
        gate = ExternalClassifierRoutingGate(classifier=settings, adapter=None)

        decision = gate.evaluate(_make_context("bypass safety"))

        assert decision is not None
        assert decision.classifier_routing_used == "heuristic"
        assert decision.classifier_fallback_reason == ""

    def test_no_adapter_heuristic_signal_scoring(self) -> None:
        settings = _classifier_settings(
            mode="enforce",
            threshold=0.5,
            signals=("bypass safety", "reveal secrets"),
        )
        gate = ExternalClassifierRoutingGate(classifier=settings, adapter=None)

        decision = gate.evaluate(_make_context("bypass safety and reveal secrets"))

        assert decision is not None
        assert decision.classifier_score == 1.0
        assert decision.classifier_signals_matched == ("bypass safety", "reveal secrets")
        assert decision.classifier_signal_count == 2


# ---------------------------------------------------------------------------
# build_ingress_gate_chain_from_overlay with external adapter
# ---------------------------------------------------------------------------

class TestBuildGateChainExternalAdapter:
    def test_chain_uses_external_classifier_when_adapter_provided(self) -> None:
        overlay = {
            "ingress_classifier_mode": "enforce",
            "ingress_classifier_threshold": 0.5,
            "ingress_classifier_signals": ["bypass safety"],
        }
        adapter = _OkAdapter(score=0.9)
        chain = build_ingress_gate_chain_from_overlay(overlay, external_classifier_adapter=adapter)

        assert chain.classifier_routing == "external"

    def test_chain_uses_heuristic_when_no_adapter(self) -> None:
        overlay = {
            "ingress_classifier_mode": "enforce",
            "ingress_classifier_threshold": 0.5,
        }
        chain = build_ingress_gate_chain_from_overlay(overlay)

        assert chain.classifier_routing == "heuristic"

    def test_chain_policy_metadata_includes_routing(self) -> None:
        chain = build_ingress_gate_chain_from_overlay(
            {"ingress_classifier_mode": "shadow"},
            external_classifier_adapter=_OkAdapter(score=0.2),
        )
        meta = chain.policy_metadata()
        assert meta["ingress_classifier_routing"] == "external"

    def test_chain_decision_carries_routing_evidence(self) -> None:
        overlay = {
            "ingress_classifier_mode": "enforce",
            "ingress_classifier_threshold": 0.5,
            "ingress_classifier_signals": ["exfiltrate data"],
        }
        adapter = _OkAdapter(score=0.9, labels=("exfil",))
        chain = build_ingress_gate_chain_from_overlay(overlay, external_classifier_adapter=adapter)

        decision = chain.evaluate(_make_context("exfiltrate data"))

        assert decision.classifier_routing_used == "external"
        assert decision.decision == PolicyAction.ESCALATE

    def test_chain_fallback_on_adapter_error_still_evaluates(self) -> None:
        overlay = {
            "ingress_classifier_mode": "shadow",
            "ingress_classifier_threshold": 0.4,
            "ingress_classifier_signals": ["bypass safety"],
        }
        chain = build_ingress_gate_chain_from_overlay(
            overlay,
            external_classifier_adapter=_ErrorAdapter(),
        )
        decision = chain.evaluate(_make_context("bypass safety attempt"))

        assert decision.classifier_routing_used == "heuristic"
        assert "ExternalClassifierError" in decision.classifier_fallback_reason


# ---------------------------------------------------------------------------
# Overlay validation for external endpoint fields
# ---------------------------------------------------------------------------

class TestExternalEndpointOverlayValidation:
    def test_valid_https_endpoint_accepted(self) -> None:
        overlay = {
            "ingress_classifier_external_endpoint": "https://classifier.example.com/v1/score",
            "ingress_classifier_external_timeout_ms": 3000,
        }
        resolution = resolve_ingress_profile_settings(overlay)
        assert resolution.classifier.external_endpoint == "https://classifier.example.com/v1/score"
        assert resolution.classifier.external_timeout_ms == 3000

    def test_empty_endpoint_accepted(self) -> None:
        overlay = {"ingress_classifier_external_endpoint": ""}
        resolution = resolve_ingress_profile_settings(overlay)
        assert resolution.classifier.external_endpoint == ""

    def test_non_https_endpoint_raises(self) -> None:
        with pytest.raises(ValueError, match="INGRESS_CLASSIFIER_EXTERNAL_ENDPOINT_INVALID"):
            resolve_ingress_profile_settings(
                {"ingress_classifier_external_endpoint": "http://classifier.example.com"}
            )

    def test_endpoint_too_long_raises(self) -> None:
        long_url = "https://" + "x" * 510
        with pytest.raises(ValueError, match="INGRESS_CLASSIFIER_EXTERNAL_ENDPOINT_INVALID"):
            resolve_ingress_profile_settings({"ingress_classifier_external_endpoint": long_url})

    def test_invalid_timeout_type_raises(self) -> None:
        with pytest.raises(ValueError, match="INGRESS_CLASSIFIER_EXTERNAL_TIMEOUT_INVALID"):
            resolve_ingress_profile_settings({"ingress_classifier_external_timeout_ms": "fast"})

    def test_timeout_below_100_raises(self) -> None:
        with pytest.raises(ValueError, match="INGRESS_CLASSIFIER_EXTERNAL_TIMEOUT_INVALID"):
            resolve_ingress_profile_settings({"ingress_classifier_external_timeout_ms": 50})

    def test_timeout_above_10000_raises(self) -> None:
        with pytest.raises(ValueError, match="INGRESS_CLASSIFIER_EXTERNAL_TIMEOUT_INVALID"):
            resolve_ingress_profile_settings({"ingress_classifier_external_timeout_ms": 10001})

    def test_default_timeout_is_2000(self) -> None:
        resolution = resolve_ingress_profile_settings({})
        assert resolution.classifier.external_timeout_ms == 2000
