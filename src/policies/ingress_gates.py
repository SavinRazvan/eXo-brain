"""
File: ingress_gates.py
Path: src/policies/ingress_gates.py
Role: Deterministic ingress gate contracts and default pre-model gate chain.
Used By:
 - src/api/bootstrap.py
 - src/api/routers/turns.py
Depends On:
 - src/schemas/tool_io.py
Notes:
 - Ingress gates run before orchestration and emit explicit allow/deny/escalate decisions.
 - Gate decisions are correlation-linked through transport-layer audit events.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace
from typing import Any, Iterable, Mapping

from src.policies.ingress_profiles import (
    IngressClassifierSettings,
    IngressCustomRule,
    resolve_ingress_profile_settings,
)

from src.schemas.tool_io import PolicyAction


@dataclass(slots=True)
class IngressTurnContext:
    tenant_id: str
    session_id: str
    correlation_id: str
    transport: str
    user_input: str
    identity_subject: str = ""
    identity_roles: list[str] = field(default_factory=list)
    identity_tenant_id: str = ""


@dataclass(slots=True)
class IngressDecision:
    schema_version: str
    decision: PolicyAction
    reason_code: str
    message: str
    gate_id: str
    gate_version: str
    review_required: bool = False
    review_channel: str = ""
    classifier_mode: str = ""
    classifier_model_version: str = ""
    classifier_score: float = 0.0
    classifier_threshold: float = 0.0
    classifier_signal_count: int = 0
    classifier_signals_matched: tuple[str, ...] = field(default_factory=tuple)
    classifier_shadow_triggered: bool = False

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "schema_version": self.schema_version,
            "decision": self.decision.value,
            "reason_code": self.reason_code,
            "message": self.message,
            "gate_id": self.gate_id,
            "gate_version": self.gate_version,
            "review_required": self.review_required,
            "review_channel": self.review_channel,
        }
        if self.classifier_mode:
            payload.update(
                {
                    "classifier_mode": self.classifier_mode,
                    "classifier_model_version": self.classifier_model_version,
                    "classifier_score": self.classifier_score,
                    "classifier_threshold": self.classifier_threshold,
                    "classifier_signal_count": self.classifier_signal_count,
                    "classifier_signals_matched": list(self.classifier_signals_matched),
                    "classifier_shadow_triggered": self.classifier_shadow_triggered,
                }
            )
        return payload


class IngressGate(ABC):
    gate_id: str = "ingress-gate"
    gate_version: str = "1.0.0"

    @abstractmethod
    def evaluate(self, context: IngressTurnContext) -> IngressDecision | None:
        """Return a non-allow decision when the gate blocks/escalates."""


@dataclass(slots=True)
class EmptyInputGate(IngressGate):
    gate_id: str = "ingress-empty-input"
    gate_version: str = "1.0.0"

    def evaluate(self, context: IngressTurnContext) -> IngressDecision | None:
        if str(context.user_input).strip():
            return None
        return IngressDecision(
            schema_version="1.0",
            decision=PolicyAction.DENY,
            reason_code="INGRESS_INPUT_EMPTY",
            message="Turn input is empty after normalization.",
            gate_id=self.gate_id,
            gate_version=self.gate_version,
        )


@dataclass(slots=True)
class MaxInputCharsGate(IngressGate):
    max_chars: int = 8000
    gate_id: str = "ingress-max-input-chars"
    gate_version: str = "1.0.0"

    def evaluate(self, context: IngressTurnContext) -> IngressDecision | None:
        normalized = str(context.user_input)
        if len(normalized) <= max(int(self.max_chars), 1):
            return None
        return IngressDecision(
            schema_version="1.0",
            decision=PolicyAction.DENY,
            reason_code="INGRESS_INPUT_TOO_LARGE",
            message=f"Turn input exceeds max allowed characters ({self.max_chars}).",
            gate_id=self.gate_id,
            gate_version=self.gate_version,
        )


@dataclass(slots=True)
class PromptInjectionHeuristicGate(IngressGate):
    escalation_phrases: tuple[str, ...] = (
        "ignore previous instructions",
        "reveal system prompt",
        "developer instructions",
        "jailbreak",
    )
    gate_id: str = "ingress-prompt-injection-heuristic"
    gate_version: str = "1.0.0"
    review_channel: str = "security-review"

    def evaluate(self, context: IngressTurnContext) -> IngressDecision | None:
        normalized_input = str(context.user_input).lower()
        matched_phrase = next(
            (phrase for phrase in self.escalation_phrases if phrase and phrase in normalized_input),
            "",
        )
        if not matched_phrase:
            return None
        return IngressDecision(
            schema_version="1.0",
            decision=PolicyAction.ESCALATE,
            reason_code="INGRESS_PROMPT_INJECTION_SUSPECTED",
            message=f"Turn input matched suspicious phrase '{matched_phrase}'.",
            gate_id=self.gate_id,
            gate_version=self.gate_version,
            review_required=True,
            review_channel=self.review_channel,
        )


@dataclass(slots=True)
class IngressClassifierHeuristicGate(IngressGate):
    classifier: IngressClassifierSettings
    gate_id: str = "ingress-classifier-heuristic"
    gate_version: str = "1.0.0"

    def evaluate(self, context: IngressTurnContext) -> IngressDecision | None:
        if not self.classifier.enabled:
            return None
        normalized_input = str(context.user_input).lower()
        matched_signals = tuple(
            signal for signal in self.classifier.signals if signal and signal in normalized_input
        )
        signal_count = max(len(self.classifier.signals), 1)
        score = round(min(1.0, len(matched_signals) / signal_count), 4)
        high_risk = bool(matched_signals) and score >= self.classifier.threshold
        if high_risk and self.classifier.mode == "enforce":
            return IngressDecision(
                schema_version="1.0",
                decision=PolicyAction.ESCALATE,
                reason_code="INGRESS_CLASSIFIER_HIGH_RISK",
                message=(
                    "Ingress classifier marked input as high-risk in enforce mode "
                    f"(score={score}, threshold={self.classifier.threshold})."
                ),
                gate_id=self.gate_id,
                gate_version=self.gate_version,
                review_required=True,
                review_channel=self.classifier.review_channel,
                classifier_mode=self.classifier.mode,
                classifier_model_version=self.classifier.model_version,
                classifier_score=score,
                classifier_threshold=self.classifier.threshold,
                classifier_signal_count=len(self.classifier.signals),
                classifier_signals_matched=matched_signals,
                classifier_shadow_triggered=False,
            )
        if high_risk and self.classifier.mode == "shadow":
            return IngressDecision(
                schema_version="1.0",
                decision=PolicyAction.ALLOW,
                reason_code="INGRESS_CLASSIFIER_SHADOW_HIGH_RISK",
                message=(
                    "Ingress classifier flagged high-risk input in shadow mode; "
                    "decision recorded without blocking."
                ),
                gate_id=self.gate_id,
                gate_version=self.gate_version,
                classifier_mode=self.classifier.mode,
                classifier_model_version=self.classifier.model_version,
                classifier_score=score,
                classifier_threshold=self.classifier.threshold,
                classifier_signal_count=len(self.classifier.signals),
                classifier_signals_matched=matched_signals,
                classifier_shadow_triggered=True,
            )
        return IngressDecision(
            schema_version="1.0",
            decision=PolicyAction.ALLOW,
            reason_code="INGRESS_CLASSIFIER_ALLOW_LOW_RISK",
            message="Ingress classifier evaluated input as low-risk.",
            gate_id=self.gate_id,
            gate_version=self.gate_version,
            classifier_mode=self.classifier.mode,
            classifier_model_version=self.classifier.model_version,
            classifier_score=score,
            classifier_threshold=self.classifier.threshold,
            classifier_signal_count=len(self.classifier.signals),
            classifier_signals_matched=matched_signals,
            classifier_shadow_triggered=False,
        )


@dataclass(slots=True)
class CustomIngressRulesGate(IngressGate):
    custom_rules: tuple[IngressCustomRule, ...] = ()
    gate_id: str = "ingress-custom-rules"
    gate_version: str = "1.0.0"

    def evaluate(self, context: IngressTurnContext) -> IngressDecision | None:
        normalized_input = str(context.user_input)
        for rule in self.custom_rules:
            if not rule.matches(normalized_input):
                continue
            if rule.action == "deny":
                return IngressDecision(
                    schema_version="1.0",
                    decision=PolicyAction.DENY,
                    reason_code=rule.reason_code,
                    message=rule.message,
                    gate_id=self.gate_id,
                    gate_version=self.gate_version,
                )
            return IngressDecision(
                schema_version="1.0",
                decision=PolicyAction.ESCALATE,
                reason_code=rule.reason_code,
                message=rule.message,
                gate_id=self.gate_id,
                gate_version=self.gate_version,
                review_required=True,
                review_channel=rule.review_channel,
            )
        return None


class IngressGateChain:
    def __init__(
        self,
        gates: Iterable[IngressGate] | None = None,
        *,
        profile_name: str = "baseline",
        custom_rule_ids: tuple[str, ...] = (),
        compatibility_mode: str = "strict",
        classifier_mode: str = "off",
        classifier_threshold: float = 0.0,
        classifier_model_version: str = "",
        classifier_signal_count: int = 0,
    ) -> None:
        self._gates: tuple[IngressGate, ...] = tuple(gates or ())
        self.profile_name = profile_name
        self.custom_rule_ids = custom_rule_ids
        self.compatibility_mode = compatibility_mode
        self.classifier_mode = classifier_mode
        self.classifier_threshold = classifier_threshold
        self.classifier_model_version = classifier_model_version
        self.classifier_signal_count = classifier_signal_count

    def evaluate(self, context: IngressTurnContext) -> IngressDecision:
        classifier_telemetry: dict[str, Any] = {}
        for gate in self._gates:
            decision = gate.evaluate(context)
            if decision is None:
                continue
            telemetry = self._extract_classifier_telemetry(decision)
            if decision.decision == PolicyAction.ALLOW:
                if telemetry:
                    classifier_telemetry = telemetry
                continue
            if decision.decision in {PolicyAction.DENY, PolicyAction.ESCALATE}:
                if not telemetry and classifier_telemetry:
                    return self._apply_classifier_telemetry(decision, classifier_telemetry)
                return decision
        decision = IngressDecision(
            schema_version="1.0",
            decision=PolicyAction.ALLOW,
            reason_code="INGRESS_ALLOW_DEFAULT",
            message="Turn allowed by ingress gate chain.",
            gate_id="ingress-gate-chain",
            gate_version="1.0.0",
        )
        if classifier_telemetry:
            return self._apply_classifier_telemetry(decision, classifier_telemetry)
        return decision

    @staticmethod
    def _extract_classifier_telemetry(decision: IngressDecision) -> dict[str, Any]:
        if not decision.classifier_mode:
            return {}
        return {
            "classifier_mode": decision.classifier_mode,
            "classifier_model_version": decision.classifier_model_version,
            "classifier_score": decision.classifier_score,
            "classifier_threshold": decision.classifier_threshold,
            "classifier_signal_count": decision.classifier_signal_count,
            "classifier_signals_matched": decision.classifier_signals_matched,
            "classifier_shadow_triggered": decision.classifier_shadow_triggered,
        }

    @staticmethod
    def _apply_classifier_telemetry(
        decision: IngressDecision,
        telemetry: Mapping[str, Any],
    ) -> IngressDecision:
        return replace(decision, **dict(telemetry))

    def policy_metadata(self) -> dict[str, Any]:
        return {
            "ingress_profile": self.profile_name,
            "ingress_custom_rule_count": len(self.custom_rule_ids),
            "ingress_custom_rule_ids": list(self.custom_rule_ids),
            "ingress_profile_compatibility_mode": self.compatibility_mode,
            "ingress_classifier_mode": self.classifier_mode,
            "ingress_classifier_threshold": self.classifier_threshold,
            "ingress_classifier_model_version": self.classifier_model_version,
            "ingress_classifier_signal_count": self.classifier_signal_count,
        }


def build_default_ingress_gate_chain() -> IngressGateChain:
    return build_ingress_gate_chain_from_overlay({})


def build_ingress_gate_chain_from_overlay(overlay: Mapping[str, Any]) -> IngressGateChain:
    resolution = resolve_ingress_profile_settings(overlay)
    custom_rule_ids = tuple(rule.rule_id for rule in resolution.custom_rules)
    return IngressGateChain(
        gates=(
            EmptyInputGate(),
            MaxInputCharsGate(max_chars=resolution.max_input_chars),
            IngressClassifierHeuristicGate(classifier=resolution.classifier),
            PromptInjectionHeuristicGate(escalation_phrases=resolution.prompt_injection_phrases),
            CustomIngressRulesGate(custom_rules=resolution.custom_rules),
        ),
        profile_name=resolution.profile_name,
        custom_rule_ids=custom_rule_ids,
        compatibility_mode=resolution.compatibility_mode,
        classifier_mode=resolution.classifier.mode,
        classifier_threshold=resolution.classifier.threshold,
        classifier_model_version=resolution.classifier.model_version,
        classifier_signal_count=len(resolution.classifier.signals),
    )
