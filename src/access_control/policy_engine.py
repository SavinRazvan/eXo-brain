"""
File: policy_engine.py
Path: src/access_control/policy_engine.py
Role: Access-control engine that evaluates tool execution authorization.
Used By:
 - src/policies/risk_gates.py
Depends On:
 - src/access_control/contracts.py
 - src/access_control/rbac.py
 - src/schemas/tool_io.py
Notes:
 - Audit-only mode records deny/escalate intent while returning allow for staged rollout.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.access_control.contracts import AccessDecision, AccessRequest
from src.access_control.rbac import aggregate_permissions
from src.schemas.tool_io import PolicyAction


@dataclass(slots=True)
class AccessControlConfig:
    role_permissions: dict[str, set[str]] = field(
        default_factory=lambda: {
            "reader": {"tool:execute"},
            "operator": {"tool:execute", "tool:execute:high_impact"},
            "admin": {"*"},
        }
    )
    review_channel: str = "security-review"
    audit_only_mode: bool = False


class AccessPolicyEngine:
    def __init__(self, config: AccessControlConfig | None = None) -> None:
        self._config = config or AccessControlConfig()

    def evaluate(self, request: AccessRequest) -> AccessDecision:
        if not request.subject:
            return self._finalize(
                AccessDecision(
                    decision=PolicyAction.DENY,
                    reason_code="ACCESS_IDENTITY_MISSING",
                    message="Identity subject is required for access control enforcement.",
                )
            )

        permissions = aggregate_permissions(request.roles, self._config.role_permissions)
        if "*" in permissions:
            return self._finalize(
                AccessDecision(
                    decision=PolicyAction.ALLOW,
                    reason_code="ACCESS_ALLOWED_ADMIN",
                    message="Access allowed via wildcard administrative permission.",
                )
            )

        required_permissions = {"tool:execute"}
        if request.is_state_changing or request.is_high_impact:
            required_permissions.add("tool:execute:high_impact")
            if "tool:execute:high_impact" not in permissions:
                return self._finalize(
                    AccessDecision(
                        decision=PolicyAction.ESCALATE,
                        reason_code="ACCESS_REVIEW_REQUIRED_HIGH_IMPACT",
                        message="High-impact operation requires elevated entitlement or review.",
                        review_required=True,
                        review_channel=self._config.review_channel,
                    )
                )

        tool_scoped_permission = f"tool:{request.tool_name}"
        if tool_scoped_permission in permissions:
            return self._finalize(
                AccessDecision(
                    decision=PolicyAction.ALLOW,
                    reason_code="ACCESS_ALLOWED_TOOL_SCOPE",
                    message="Access allowed via tool-scoped permission.",
                )
            )

        if not required_permissions.issubset(permissions):
            return self._finalize(
                AccessDecision(
                    decision=PolicyAction.DENY,
                    reason_code="ACCESS_DENIED_ROLE_MISSING_PERMISSION",
                    message="Role permissions do not allow this operation.",
                )
            )

        return self._finalize(
            AccessDecision(
                decision=PolicyAction.ALLOW,
                reason_code="ACCESS_ALLOWED_BASE_PERMISSION",
                message="Access allowed via base execution permission.",
            )
        )

    def _finalize(self, decision: AccessDecision) -> AccessDecision:
        if not self._config.audit_only_mode:
            return decision
        if decision.decision == PolicyAction.ALLOW:
            return decision
        metadata = dict(decision.metadata)
        metadata["audit_only_original_decision"] = decision.decision.value
        return AccessDecision(
            decision=PolicyAction.ALLOW,
            reason_code="ACCESS_AUDIT_ONLY_BYPASS",
            message=f"Audit-only mode bypassed '{decision.reason_code}'.",
            review_required=False,
            review_channel=None,
            metadata=metadata,
        )

