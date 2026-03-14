"""
File: tenant_schemas.py
Path: src/api/schemas/tenant_schemas.py
Role: Pydantic schemas for tenant policy overlay and quota management endpoints.
Used By:
 - src/api/routers/tenants.py
Depends On:
 - pydantic
Notes:
 - PolicyOverlayRequest is an open dict so the overlay format can evolve
   without a schema version bump. Validation is done at policy middleware application.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator

from src.policies.ingress_profiles import resolve_ingress_profile_settings


class PolicyOverlayRequest(BaseModel):
    """Tenant policy overlay to apply immediately on the next tool call.

    Common fields (all optional):
      deny_tools: list of tool names to block unconditionally.
      escalate_risk_tiers: list of risk tier names whose calls require escalation.
      escalate_state_changing: if true, all state-changing calls are escalated.

    Governance ingress extension fields (inside `extra`):
      ingress_profile: one of ["baseline", "strict", "hardened"].
      ingress_max_input_chars: custom max-input threshold that can only tighten profile baseline.
      ingress_prompt_injection_phrases: custom suspicious phrase set that must include profile baseline phrases.
      ingress_custom_rules: list of object rules with shape:
        {
          "rule_id": "non-empty-id",
          "action": "deny|escalate",
          "match_type": "contains_any|regex_any",
          "patterns": ["..."],
          "reason_code": "OPTIONAL_REASON_CODE",
          "message": "OPTIONAL_MESSAGE",
          "case_sensitive": false,
          "review_channel": "security-review"
        }
      signed_gate_plugin_ref: signed enterprise plugin reference (Enterprise only).
    """

    deny_tools: list[str] = Field(default_factory=list)
    escalate_risk_tiers: list[str] = Field(default_factory=list)
    escalate_state_changing: bool = False
    extra: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_ingress_overlay_compatibility(self) -> "PolicyOverlayRequest":
        overlay = {
            "deny_tools": self.deny_tools,
            "escalate_risk_tiers": self.escalate_risk_tiers,
            "escalate_state_changing": self.escalate_state_changing,
            **self.extra,
        }
        resolve_ingress_profile_settings(overlay)
        return self


class PolicyOverlayResponse(BaseModel):
    """Current active policy overlay for a tenant.

    Returns an empty overlay if none has been set.
    """

    tenant_id: str
    overlay: dict[str, Any]


class QuotaResponse(BaseModel):
    """Current quota configuration and live counters for a tenant."""

    tenant_id: str
    max_active_jobs: int = Field(
        description="Configured limit for concurrent background jobs. 0 means unlimited."
    )
    active_jobs: int = Field(
        default=0,
        description="Number of currently running background jobs. "
        "Live tracking is scoped to BackgroundRuntime; returns 0 if not wired.",
    )


class QuotaUpdateRequest(BaseModel):
    """Update the concurrent job limit for a tenant."""

    max_active_jobs: int = Field(
        ge=0,
        description="New limit for concurrent background jobs. 0 means unlimited.",
    )
