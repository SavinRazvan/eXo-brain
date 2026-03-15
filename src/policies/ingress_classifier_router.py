"""
File: ingress_classifier_router.py
Path: src/policies/ingress_classifier_router.py
Role: Provider-neutral external classifier adapter contract and routing result dataclass.
Used By:
 - src/policies/ingress_gates.py
Depends On:
 - dataclasses
 - abc
Notes:
 - ExternalClassifierAdapter is the contract all external classifiers must implement.
 - ClassifierRoutingResult carries the result plus routing evidence (which path was used,
   fallback reason, latency). This keeps routing observability in-band with the decision.
 - All implementations must be deterministic and side-effect-free. Adapters may call
   external HTTP endpoints but must honour the timeout_ms contract.
 - Fallback to the heuristic gate happens transparently when the adapter raises or times out.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Contract
# ---------------------------------------------------------------------------

class ExternalClassifierAdapter(ABC):
    """Provider-neutral interface for an external turn-ingress classifier.

    Implementations may call HTTP endpoints, gRPC services, or any other
    transport. They must respect ``timeout_ms`` and raise on failure so the
    routing gate can fall back to the heuristic.
    """

    @property
    @abstractmethod
    def adapter_id(self) -> str:
        """Stable identifier for this adapter (used in routing evidence)."""

    @abstractmethod
    def classify(
        self,
        user_input: str,
        *,
        timeout_ms: int = 2000,
    ) -> "ExternalClassifierResult":
        """Classify ``user_input`` and return a structured result.

        Args:
            user_input: Normalised turn input text.
            timeout_ms:  Hard timeout for the external call.

        Returns:
            ExternalClassifierResult with score, labels, and model version.

        Raises:
            ExternalClassifierError: On any transport or upstream failure.
            TimeoutError: When the adapter exceeds ``timeout_ms``.
        """


# ---------------------------------------------------------------------------
# Adapter result
# ---------------------------------------------------------------------------

@dataclass(slots=True, frozen=True)
class ExternalClassifierResult:
    """Result returned by an ExternalClassifierAdapter.

    Attributes:
        score:         Risk score in [0.0, 1.0].
        labels:        Risk labels assigned by the external model (immutable tuple).
        model_version: Version string reported by the external model.
        latency_ms:    Wall-clock time spent in the adapter call (milliseconds).
    """

    score: float
    labels: tuple[str, ...] = field(default_factory=tuple)
    model_version: str = ""
    latency_ms: int = 0

    def __post_init__(self) -> None:
        if not (0.0 <= self.score <= 1.0):
            raise ValueError(
                f"EXTERNAL_CLASSIFIER_SCORE_INVALID: score must be in [0,1], got {self.score}"
            )


# ---------------------------------------------------------------------------
# Routing result — wraps either the external or heuristic outcome
# ---------------------------------------------------------------------------

@dataclass(slots=True, frozen=True)
class ClassifierRoutingResult:
    """Carries classification outcome plus routing evidence.

    This dataclass is the authoritative evidence record produced by
    ExternalClassifierRoutingGate. It covers both the "external path used"
    and "fell back to heuristic" cases.

    Attributes:
        score:            Final risk score used in the gate decision.
        model_version:    Model/version label used (external or heuristic).
        labels:           Risk labels (from external model; empty for heuristic path).
        routing_used:     Which routing path was taken: ``"external"`` | ``"heuristic"``.
        fallback_reason:  Non-empty when heuristic fallback was triggered; human-readable.
        external_latency_ms: Elapsed time for the external adapter call (0 on heuristic path).
        signals_matched:  Matched heuristic signals (empty on external path).
        signal_count:     Total heuristic signal count (0 on external path).
    """

    score: float
    model_version: str
    routing_used: str
    labels: tuple[str, ...] = field(default_factory=tuple)
    fallback_reason: str = ""
    external_latency_ms: int = 0
    signals_matched: tuple[str, ...] = field(default_factory=tuple)
    signal_count: int = 0

    @property
    def used_external(self) -> bool:
        return self.routing_used == "external"

    @property
    def used_fallback(self) -> bool:
        return bool(self.fallback_reason)


# ---------------------------------------------------------------------------
# Error type
# ---------------------------------------------------------------------------

class ExternalClassifierError(RuntimeError):
    """Raised by ExternalClassifierAdapter implementations on upstream failure."""
