"""
File: ingress_gates.py
Path: src/policies/ingress_gates.py
Role: Deterministic ingress gate contracts and default pre-model gate chain.
Used By:
 - src/api/bootstrap.py
 - src/api/routers/turns.py
Depends On:
 - src/policies/ingress_classifier_router.py
 - src/schemas/tool_io.py
Notes:
 - Ingress gates run before orchestration and emit explicit allow/deny/escalate decisions.
 - Gate decisions are correlation-linked through transport-layer audit events.
 - ExternalClassifierRoutingGate routes to an external classifier when configured and
   falls back transparently to the heuristic gate on timeout or failure. Routing evidence
   (routing_used, fallback_reason, external_latency_ms) is included in IngressDecision.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace
from typing import Any, Iterable, Mapping

from src.policies.ingress_classifier_router import (
    ClassifierRoutingResult,
    ExternalClassifierAdapter,
    ExternalClassifierError,
)
from src.policies.ingress_profiles import (
    IngressClassifierSettings,
    IngressCustomRule,
    resolve_ingress_profile_settings,
)
from src.policies.ingress_signed_plugins import SignedIngressPlugin

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
    # External classifier routing evidence
    classifier_routing_used: str = ""
    classifier_fallback_reason: str = ""
    classifier_external_latency_ms: int = 0
    classifier_labels: tuple[str, ...] = field(default_factory=tuple)
    signed_plugin_ref: str = ""
    signed_plugin_version: str = ""
    signed_plugin_signer: str = ""
    signed_plugin_rule_id: str = ""
    signed_plugin_rule_action: str = ""
    signed_plugin_sandbox_mode: str = ""
    signed_plugin_matched: bool = False

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
        if self.classifier_routing_used:
            payload.update(
                {
                    "classifier_routing_used": self.classifier_routing_used,
                    "classifier_fallback_reason": self.classifier_fallback_reason,
                    "classifier_external_latency_ms": self.classifier_external_latency_ms,
                    "classifier_labels": list(self.classifier_labels),
                }
            )
        if self.signed_plugin_ref:
            payload.update(
                {
                    "signed_plugin_ref": self.signed_plugin_ref,
                    "signed_plugin_version": self.signed_plugin_version,
                    "signed_plugin_signer": self.signed_plugin_signer,
                    "signed_plugin_rule_id": self.signed_plugin_rule_id,
                    "signed_plugin_rule_action": self.signed_plugin_rule_action,
                    "signed_plugin_sandbox_mode": self.signed_plugin_sandbox_mode,
                    "signed_plugin_matched": self.signed_plugin_matched,
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
class ExternalClassifierRoutingGate(IngressGate):
    """Routes to an external classifier adapter with transparent heuristic fallback.

    When ``adapter`` is provided and ``classifier.enabled`` is True, the gate
    calls the adapter. On timeout or error it falls back to the heuristic scoring
    logic. Routing evidence (routing_used, fallback_reason, external_latency_ms,
    labels) is embedded in every IngressDecision this gate emits.
    """

    classifier: IngressClassifierSettings
    adapter: ExternalClassifierAdapter | None = None
    gate_id: str = "ingress-external-classifier-routing"
    gate_version: str = "1.0.0"

    def evaluate(self, context: IngressTurnContext) -> IngressDecision | None:
        if not self.classifier.enabled:
            return None

        routing_result = self._route(str(context.user_input))
        high_risk = routing_result.score >= self.classifier.threshold

        if high_risk and self.classifier.mode == "enforce":
            return self._build_decision(
                action=PolicyAction.ESCALATE,
                reason_code="INGRESS_CLASSIFIER_HIGH_RISK",
                message=(
                    "Ingress classifier marked input as high-risk in enforce mode "
                    f"(score={routing_result.score}, threshold={self.classifier.threshold}, "
                    f"routing={routing_result.routing_used})."
                ),
                routing=routing_result,
                review_required=True,
                shadow_triggered=False,
            )

        if high_risk and self.classifier.mode == "shadow":
            return self._build_decision(
                action=PolicyAction.ALLOW,
                reason_code="INGRESS_CLASSIFIER_SHADOW_HIGH_RISK",
                message=(
                    "Ingress classifier flagged high-risk input in shadow mode; "
                    "decision recorded without blocking."
                ),
                routing=routing_result,
                shadow_triggered=True,
            )

        return self._build_decision(
            action=PolicyAction.ALLOW,
            reason_code="INGRESS_CLASSIFIER_ALLOW_LOW_RISK",
            message="Ingress classifier evaluated input as low-risk.",
            routing=routing_result,
            shadow_triggered=False,
        )

    def _route(self, user_input: str) -> ClassifierRoutingResult:
        """Attempt the external adapter; fall back to heuristic on any failure."""
        if self.adapter is not None:
            start = time.monotonic()
            try:
                ext_result = self.adapter.classify(
                    user_input,
                    timeout_ms=2000,
                )
                latency_ms = int((time.monotonic() - start) * 1000)
                return ClassifierRoutingResult(
                    score=ext_result.score,
                    model_version=ext_result.model_version or self.classifier.model_version,
                    routing_used="external",
                    labels=ext_result.labels,
                    external_latency_ms=latency_ms,
                )
            except (ExternalClassifierError, TimeoutError, Exception) as exc:
                latency_ms = int((time.monotonic() - start) * 1000)
                fallback_reason = f"{type(exc).__name__}: {exc}"
                return self._heuristic_result(
                    user_input,
                    fallback_reason=fallback_reason,
                    external_latency_ms=latency_ms,
                )

        return self._heuristic_result(user_input, fallback_reason="", external_latency_ms=0)

    def _heuristic_result(
        self,
        user_input: str,
        *,
        fallback_reason: str,
        external_latency_ms: int,
    ) -> ClassifierRoutingResult:
        normalized_input = user_input.lower()
        matched_signals = tuple(
            s for s in self.classifier.signals if s and s in normalized_input
        )
        signal_count = max(len(self.classifier.signals), 1)
        score = round(min(1.0, len(matched_signals) / signal_count), 4)
        return ClassifierRoutingResult(
            score=score,
            model_version=self.classifier.model_version,
            routing_used="heuristic",
            fallback_reason=fallback_reason,
            external_latency_ms=external_latency_ms,
            signals_matched=matched_signals,
            signal_count=len(self.classifier.signals),
        )

    def _build_decision(
        self,
        *,
        action: PolicyAction,
        reason_code: str,
        message: str,
        routing: ClassifierRoutingResult,
        review_required: bool = False,
        shadow_triggered: bool = False,
    ) -> IngressDecision:
        return IngressDecision(
            schema_version="1.0",
            decision=action,
            reason_code=reason_code,
            message=message,
            gate_id=self.gate_id,
            gate_version=self.gate_version,
            review_required=review_required,
            review_channel=self.classifier.review_channel if review_required else "",
            classifier_mode=self.classifier.mode,
            classifier_model_version=routing.model_version,
            classifier_score=routing.score,
            classifier_threshold=self.classifier.threshold,
            classifier_signal_count=routing.signal_count,
            classifier_signals_matched=routing.signals_matched,
            classifier_shadow_triggered=shadow_triggered,
            classifier_routing_used=routing.routing_used,
            classifier_fallback_reason=routing.fallback_reason,
            classifier_external_latency_ms=routing.external_latency_ms,
            classifier_labels=routing.labels,
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


@dataclass(slots=True)
class SignedPluginIngressGate(IngressGate):
    plugin: SignedIngressPlugin | None = None
    gate_id: str = "ingress-signed-plugin"
    gate_version: str = "1.0.0"

    def evaluate(self, context: IngressTurnContext) -> IngressDecision | None:
        if self.plugin is None:
            return None
        normalized_input = str(context.user_input)
        manifest = self.plugin.manifest
        for rule in self.plugin.rules:
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
                    signed_plugin_ref=manifest.plugin_ref,
                    signed_plugin_version=manifest.version,
                    signed_plugin_signer=manifest.signer,
                    signed_plugin_rule_id=rule.rule_id,
                    signed_plugin_rule_action=rule.action,
                    signed_plugin_sandbox_mode=manifest.sandbox_mode,
                    signed_plugin_matched=True,
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
                signed_plugin_ref=manifest.plugin_ref,
                signed_plugin_version=manifest.version,
                signed_plugin_signer=manifest.signer,
                signed_plugin_rule_id=rule.rule_id,
                signed_plugin_rule_action=rule.action,
                signed_plugin_sandbox_mode=manifest.sandbox_mode,
                signed_plugin_matched=True,
            )
        return IngressDecision(
            schema_version="1.0",
            decision=PolicyAction.ALLOW,
            reason_code="INGRESS_SIGNED_PLUGIN_ALLOW_NO_MATCH",
            message="Signed ingress plugin evaluated input with no matching rule.",
            gate_id=self.gate_id,
            gate_version=self.gate_version,
            signed_plugin_ref=manifest.plugin_ref,
            signed_plugin_version=manifest.version,
            signed_plugin_signer=manifest.signer,
            signed_plugin_sandbox_mode=manifest.sandbox_mode,
            signed_plugin_matched=False,
        )


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
        classifier_routing: str = "",
        signed_plugin_ref: str = "",
        signed_plugin_version: str = "",
        signed_plugin_signer: str = "",
        signed_plugin_sandbox_mode: str = "",
        signed_plugin_rule_count: int = 0,
    ) -> None:
        self._gates: tuple[IngressGate, ...] = tuple(gates or ())
        self.profile_name = profile_name
        self.custom_rule_ids = custom_rule_ids
        self.compatibility_mode = compatibility_mode
        self.classifier_mode = classifier_mode
        self.classifier_threshold = classifier_threshold
        self.classifier_model_version = classifier_model_version
        self.classifier_signal_count = classifier_signal_count
        self.classifier_routing = classifier_routing
        self.signed_plugin_ref = signed_plugin_ref
        self.signed_plugin_version = signed_plugin_version
        self.signed_plugin_signer = signed_plugin_signer
        self.signed_plugin_sandbox_mode = signed_plugin_sandbox_mode
        self.signed_plugin_rule_count = signed_plugin_rule_count

    def evaluate(self, context: IngressTurnContext) -> IngressDecision:
        allow_telemetry: dict[str, Any] = {}
        for gate in self._gates:
            decision = gate.evaluate(context)
            if decision is None:
                continue
            telemetry = self._extract_allow_telemetry(decision)
            if decision.decision == PolicyAction.ALLOW:
                if telemetry:
                    allow_telemetry = self._merge_allow_telemetry(allow_telemetry, telemetry)
                continue
            if decision.decision in {PolicyAction.DENY, PolicyAction.ESCALATE}:
                if allow_telemetry:
                    return self._apply_allow_telemetry(decision, allow_telemetry)
                return decision
        decision = IngressDecision(
            schema_version="1.0",
            decision=PolicyAction.ALLOW,
            reason_code="INGRESS_ALLOW_DEFAULT",
            message="Turn allowed by ingress gate chain.",
            gate_id="ingress-gate-chain",
            gate_version="1.0.0",
        )
        if allow_telemetry:
            return self._apply_allow_telemetry(decision, allow_telemetry)
        return decision

    @staticmethod
    def _extract_allow_telemetry(decision: IngressDecision) -> dict[str, Any]:
        telemetry: dict[str, Any] = {}
        if decision.classifier_mode:
            telemetry.update(
                {
                    "classifier_mode": decision.classifier_mode,
                    "classifier_model_version": decision.classifier_model_version,
                    "classifier_score": decision.classifier_score,
                    "classifier_threshold": decision.classifier_threshold,
                    "classifier_signal_count": decision.classifier_signal_count,
                    "classifier_signals_matched": decision.classifier_signals_matched,
                    "classifier_shadow_triggered": decision.classifier_shadow_triggered,
                    "classifier_routing_used": decision.classifier_routing_used,
                    "classifier_fallback_reason": decision.classifier_fallback_reason,
                    "classifier_external_latency_ms": decision.classifier_external_latency_ms,
                    "classifier_labels": decision.classifier_labels,
                }
            )
        if decision.signed_plugin_ref:
            telemetry.update(
                {
                    "signed_plugin_ref": decision.signed_plugin_ref,
                    "signed_plugin_version": decision.signed_plugin_version,
                    "signed_plugin_signer": decision.signed_plugin_signer,
                    "signed_plugin_rule_id": decision.signed_plugin_rule_id,
                    "signed_plugin_rule_action": decision.signed_plugin_rule_action,
                    "signed_plugin_sandbox_mode": decision.signed_plugin_sandbox_mode,
                    "signed_plugin_matched": decision.signed_plugin_matched,
                }
            )
        return telemetry

    @staticmethod
    def _merge_allow_telemetry(
        existing: Mapping[str, Any],
        incoming: Mapping[str, Any],
    ) -> dict[str, Any]:
        merged = dict(existing)
        if incoming.get("classifier_mode"):
            merged.update(
                {
                    "classifier_mode": incoming.get("classifier_mode", ""),
                    "classifier_model_version": incoming.get("classifier_model_version", ""),
                    "classifier_score": incoming.get("classifier_score", 0.0),
                    "classifier_threshold": incoming.get("classifier_threshold", 0.0),
                    "classifier_signal_count": incoming.get("classifier_signal_count", 0),
                    "classifier_signals_matched": incoming.get("classifier_signals_matched", ()),
                    "classifier_shadow_triggered": incoming.get("classifier_shadow_triggered", False),
                    "classifier_routing_used": incoming.get("classifier_routing_used", ""),
                    "classifier_fallback_reason": incoming.get("classifier_fallback_reason", ""),
                    "classifier_external_latency_ms": incoming.get("classifier_external_latency_ms", 0),
                    "classifier_labels": incoming.get("classifier_labels", ()),
                }
            )
        if incoming.get("signed_plugin_ref"):
            merged.update(
                {
                    "signed_plugin_ref": incoming.get("signed_plugin_ref", ""),
                    "signed_plugin_version": incoming.get("signed_plugin_version", ""),
                    "signed_plugin_signer": incoming.get("signed_plugin_signer", ""),
                    "signed_plugin_rule_id": incoming.get("signed_plugin_rule_id", ""),
                    "signed_plugin_rule_action": incoming.get("signed_plugin_rule_action", ""),
                    "signed_plugin_sandbox_mode": incoming.get("signed_plugin_sandbox_mode", ""),
                    "signed_plugin_matched": incoming.get("signed_plugin_matched", False),
                }
            )
        return merged

    @staticmethod
    def _apply_allow_telemetry(
        decision: IngressDecision,
        telemetry: Mapping[str, Any],
    ) -> IngressDecision:
        updates: dict[str, Any] = {}
        if not decision.classifier_mode and telemetry.get("classifier_mode"):
            updates.update(
                {
                    "classifier_mode": telemetry.get("classifier_mode", ""),
                    "classifier_model_version": telemetry.get("classifier_model_version", ""),
                    "classifier_score": telemetry.get("classifier_score", 0.0),
                    "classifier_threshold": telemetry.get("classifier_threshold", 0.0),
                    "classifier_signal_count": telemetry.get("classifier_signal_count", 0),
                    "classifier_signals_matched": telemetry.get("classifier_signals_matched", ()),
                    "classifier_shadow_triggered": telemetry.get("classifier_shadow_triggered", False),
                    "classifier_routing_used": telemetry.get("classifier_routing_used", ""),
                    "classifier_fallback_reason": telemetry.get("classifier_fallback_reason", ""),
                    "classifier_external_latency_ms": telemetry.get("classifier_external_latency_ms", 0),
                    "classifier_labels": telemetry.get("classifier_labels", ()),
                }
            )
        if not decision.signed_plugin_ref and telemetry.get("signed_plugin_ref"):
            updates.update(
                {
                    "signed_plugin_ref": telemetry.get("signed_plugin_ref", ""),
                    "signed_plugin_version": telemetry.get("signed_plugin_version", ""),
                    "signed_plugin_signer": telemetry.get("signed_plugin_signer", ""),
                    "signed_plugin_rule_id": telemetry.get("signed_plugin_rule_id", ""),
                    "signed_plugin_rule_action": telemetry.get("signed_plugin_rule_action", ""),
                    "signed_plugin_sandbox_mode": telemetry.get("signed_plugin_sandbox_mode", ""),
                    "signed_plugin_matched": telemetry.get("signed_plugin_matched", False),
                }
            )
        if not updates:
            return decision
        return replace(decision, **updates)

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
            "ingress_classifier_routing": self.classifier_routing,
            "signed_gate_plugin_ref": self.signed_plugin_ref,
            "signed_gate_plugin_version": self.signed_plugin_version,
            "signed_gate_plugin_signer": self.signed_plugin_signer,
            "signed_gate_plugin_sandbox_mode": self.signed_plugin_sandbox_mode,
            "signed_gate_plugin_rule_count": self.signed_plugin_rule_count,
        }


def build_default_ingress_gate_chain() -> IngressGateChain:
    return build_ingress_gate_chain_from_overlay({})


def build_ingress_gate_chain_from_overlay(
    overlay: Mapping[str, Any],
    *,
    external_classifier_adapter: ExternalClassifierAdapter | None = None,
) -> IngressGateChain:
    resolution = resolve_ingress_profile_settings(overlay)
    custom_rule_ids = tuple(rule.rule_id for rule in resolution.custom_rules)
    signed_plugin = resolution.signed_plugin

    # Use ExternalClassifierRoutingGate when an adapter is provided; it falls back
    # to heuristic internally. Otherwise keep the deterministic heuristic gate.
    if external_classifier_adapter is not None:
        classifier_gate: IngressGate = ExternalClassifierRoutingGate(
            classifier=resolution.classifier,
            adapter=external_classifier_adapter,
        )
        classifier_routing = "external"
    else:
        classifier_gate = IngressClassifierHeuristicGate(classifier=resolution.classifier)
        classifier_routing = "heuristic"

    return IngressGateChain(
        gates=(
            EmptyInputGate(),
            MaxInputCharsGate(max_chars=resolution.max_input_chars),
            classifier_gate,
            PromptInjectionHeuristicGate(escalation_phrases=resolution.prompt_injection_phrases),
            CustomIngressRulesGate(custom_rules=resolution.custom_rules),
            SignedPluginIngressGate(plugin=signed_plugin),
        ),
        profile_name=resolution.profile_name,
        custom_rule_ids=custom_rule_ids,
        compatibility_mode=resolution.compatibility_mode,
        classifier_mode=resolution.classifier.mode,
        classifier_threshold=resolution.classifier.threshold,
        classifier_model_version=resolution.classifier.model_version,
        classifier_signal_count=len(resolution.classifier.signals),
        classifier_routing=classifier_routing,
        signed_plugin_ref=signed_plugin.manifest.plugin_ref if signed_plugin else "",
        signed_plugin_version=signed_plugin.manifest.version if signed_plugin else "",
        signed_plugin_signer=signed_plugin.manifest.signer if signed_plugin else "",
        signed_plugin_sandbox_mode=signed_plugin.manifest.sandbox_mode if signed_plugin else "",
        signed_plugin_rule_count=len(signed_plugin.rules) if signed_plugin else 0,
    )
