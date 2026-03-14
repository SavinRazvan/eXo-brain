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
      ingress_classifier_mode: "off" | "shadow" | "enforce" (Pro+).
      ingress_classifier_threshold: float in [0,1] controlling risk trigger threshold.
      ingress_classifier_model_version: telemetry model-version label (for deterministic classifier profile).
      ingress_classifier_signals: list of classifier signal phrases (max 64).
      ingress_classifier_review_channel: escalation channel used when classifier enforce mode triggers.
      signed_gate_plugin_ref: signed enterprise plugin reference from trusted registry
        (for example `plugin://trusted/signed-v1` or `plugin://trusted/signed-v2`).
        Plugin lifecycle is guarded as follows:
        - load is allowed immediately for next turn,
        - unload/reload is blocked while active runs exist for the tenant,
        - plugin payload stays declarative-only under sandbox policy checks.
      Note: plugin version/signer/signature metadata is normalized server-side from the
        signed plugin registry and should not be client-authored.
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


class PolicyTemplateSummary(BaseModel):
    """Catalog metadata for a packaged governance policy template."""

    template_id: str
    packaged_risk_profile_id: str
    title: str
    description: str
    minimum_tier: str
    ingress_profile: str
    ingress_classifier_mode: str
    ingress_custom_rule_count: int
    includes_signed_plugin: bool


class PolicyTemplateListResponse(BaseModel):
    """Template catalog for tenant-level packaged policy profiles."""

    tenant_id: str
    templates: list[PolicyTemplateSummary]


class PolicyTemplateApplyRequest(BaseModel):
    """Apply a packaged policy template to tenant overlay state.

    merge_with_existing:
      - false: replace with packaged template baseline + normalized ingress patch.
      - true: start from existing overlay, then apply packaged template overrides.
    extra:
      - optional non-ingress overrides merged after the template.
      - ingress-governed keys are locked by template and rejected if provided.
    """

    merge_with_existing: bool = False
    extra: dict[str, Any] = Field(default_factory=dict)


class PolicyTemplateApplyResponse(BaseModel):
    """Result payload for template application endpoint."""

    tenant_id: str
    template_id: str
    packaged_risk_profile_id: str
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
