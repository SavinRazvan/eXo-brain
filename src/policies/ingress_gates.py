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
from dataclasses import dataclass, field
from typing import Iterable

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

    def to_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "decision": self.decision.value,
            "reason_code": self.reason_code,
            "message": self.message,
            "gate_id": self.gate_id,
            "gate_version": self.gate_version,
            "review_required": self.review_required,
            "review_channel": self.review_channel,
        }


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


class IngressGateChain:
    def __init__(self, gates: Iterable[IngressGate] | None = None) -> None:
        self._gates: tuple[IngressGate, ...] = tuple(gates or ())

    def evaluate(self, context: IngressTurnContext) -> IngressDecision:
        for gate in self._gates:
            decision = gate.evaluate(context)
            if decision is None:
                continue
            if decision.decision in {PolicyAction.DENY, PolicyAction.ESCALATE}:
                return decision
        return IngressDecision(
            schema_version="1.0",
            decision=PolicyAction.ALLOW,
            reason_code="INGRESS_ALLOW_DEFAULT",
            message="Turn allowed by ingress gate chain.",
            gate_id="ingress-gate-chain",
            gate_version="1.0.0",
        )


def build_default_ingress_gate_chain() -> IngressGateChain:
    return IngressGateChain(
        gates=(
            EmptyInputGate(),
            MaxInputCharsGate(),
            PromptInjectionHeuristicGate(),
        )
    )
