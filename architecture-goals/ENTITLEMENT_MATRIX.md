<!--
File: ENTITLEMENT_MATRIX.md
Path: architecture-goals/ENTITLEMENT_MATRIX.md
Role: Enforceable feature-to-tier entitlement mapping for monetization and enterprise packaging.
Used By:
 - architecture-goals/MONETIZATION_STRATEGY.md
 - architecture-goals/DEPLOYMENT_MODELS.md
 - architecture-goals/TRACEABILITY_MATRIX.md
Depends On:
 - src/api/routers/*
 - src/policies/*
 - src/config/settings.py
 - tests/modules/*
Notes:
 - This file defines target enforcement points and evidence expectations.
 - Items marked Planned require implementation before commercial entitlement claims.
-->

# Entitlement Matrix

## Governance Metadata

- Status: `active`
- Owner: `Savin I. Razvan`
- Version: `1.0.0`
- Last Reviewed: `2026-03-12`
- Review Cadence: `monthly`
- Decision Scope: `Feature-to-tier packaging, enforcement surfaces, and evidence requirements for commercial operations.`

## 1) Purpose

Translate tier strategy into enforceable product controls.

Each row maps:
- tiered capability,
- concrete enforcement surface (API/config/policy),
- minimum test evidence,
- minimum audit/evidence expectation,
- non-bypass constraints.

---

## 2) Tier Definitions

- `Foundation`: trusted baseline required for safe adoption.
- `Pro`: production governance depth and advanced operational controls.
- `Enterprise`: compliance-grade evidence workflows, strict controls, and premium operational assurances.

---

## 3) Entitlement Contract

Rules:

1. Safety baseline features must not be paywalled in a way that weakens trust.
2. Premium tiers may expand control depth, observability depth, and compliance assurance.
3. Entitlement checks must be explicit at API/config/policy boundaries.
4. Any premium claim must cite at least one test anchor and one evidence anchor.

Current status:
- Tier intent is defined.
- Full entitlement enforcement middleware is `Planned`.

---

## 4) Feature-to-Tier Matrix

| Capability | Tier | Enforcement surface (API/config/policy) | Current state | Test evidence | Audit/evidence anchor | Non-bypass constraint | Notes / blockers |
|---|---|---|---|---|---|---|---|
| Provider-neutral adapter registration and selection | Foundation | `POST/GET/DELETE /providers*`, `src/config/provider_registry.py` | Enforceable | `tests/modules/api/test_slice_provider_registration.py`, `tests/modules/config/test_provider_registry.py` | provider health/capability endpoints evidence | Must remain contract/capability-based, not provider-name hardcoded in core | Baseline adoption capability |
| Deterministic policy-governed tool path | Foundation | `src/tools/executor.py`, `src/policies/middleware.py`, mode selection in `src/runtime/mode_selector.py` | Enforceable | `tests/modules/policies/test_policy_risk_gates.py`, `tests/modules/policies/test_deterministic_tool_replay.py`, `tests/modules/core/test_orchestrator_turn.py` | runtime events + policy outcomes in audit chain | Risky/state-changing calls cannot bypass policy + deterministic executor | Core trust baseline |
| Tenant policy overlay controls | Foundation | `GET/PUT /{tenant_id}/policy`, `src/tenancy/policy_overlay.py` | Enforceable | `tests/modules/api/test_slice4_tenant_policy.py` | policy change and outcome visibility via runtime/audit APIs | Overlay must not bypass core policy middleware | Baseline governance configurability |
| Tenant quota controls | Foundation | `GET/PUT /{tenant_id}/quota`, `src/tenancy/quotas.py` | Enforceable | `tests/modules/core/test_tenant_quota_enforcement.py`, `tests/modules/api/test_slice4_tenant_policy.py` | runtime control stats and run outcomes | Quota checks remain tenant-scoped | `active_jobs` live tracking is post-v1 improvement |
| Core audit events/report access | Foundation | `GET /admin/audit/events`, `GET /admin/audit/report` | Enforceable | `tests/modules/api/test_audit_api.py` | audit report payloads | Audit collection cannot be disabled on risky paths | Baseline observability for operations |
| Advanced runtime admin controls | Pro | `src/api/routers/runtime_control.py` (`/admin/runtime/*`) | Enforceable | `tests/modules/api/test_runtime_control_api.py`, `tests/modules/api/test_byoc_runtime_control_api.py` | runtime control stats and cancellation records | Must remain authz + tenant-scoped | Pro operations depth |
| Advanced fallback/routing governance | Pro | `/{tenant_id}/agents/routes`, `/{tenant_id}/agents/fallback` | Enforceable | `tests/modules/agents/test_orchestrator_agent_handoff.py`, `tests/modules/api/test_slice2_tools_agents.py` | route/fallback behavior visible in run traces | Fallback cannot reduce deterministic safety posture | Pro orchestration control |
| BYOC governance analytics and anomaly reporting | Pro | `/{tenant_id}/admin/byoc/governance-metrics`, `src/policies/governance_anomaly_detector.py` | Enforceable | `tests/modules/policies/test_governance_anomaly_detector.py` | governance metrics endpoint payloads | Advisory analytics cannot bypass policy decisions | Pro governance insight |
| Policy templates and packaged risk profiles | Pro | Planned policy-pack API/config layer | Planned | Planned: policy-pack contract tests | Planned: policy-pack audit trail | Templates must compile to standard policy overlay/gate paths | Requires template registry and entitlement gate implementation |
| Signed audit export and verification workflow | Enterprise | `POST /admin/audit/export-file`, `POST /admin/audit/verify` | Enforceable | `tests/modules/audit/test_evidence_bundle_generation.py`, `tests/modules/audit/test_audit_chain_integrity.py`, `tests/modules/api/test_audit_api.py` | signed bundle artifacts and verify responses | Signature/chain verification must remain server-side | Enterprise compliance-ready evidence |
| Advanced fairness/admission controls | Enterprise | `src/policies/byoc_fairness.py`, runtime settings in `src/config/settings.py` | Enforceable (feature-flagged) | `tests/modules/policies/test_byoc_fairness.py`, `tests/modules/tools/test_byoc_non_blocking_execute.py` | runtime stats and governance metrics | Fairness cannot weaken tenant isolation or policy controls | Enterprise scale governance |
| Enterprise release signoff evidence bundle | Enterprise | `scripts/release/verify_gates.py`, `make rc-signoff*` | Enforceable | `tests/modules/unknown/test_release_scripts.py` | RC signoff artifacts | Release cannot skip P0 gates | Enterprise operational assurance |
| Entitlement middleware and hard API gating by tier | Cross-tier | Planned entitlement layer (API middleware / policy gate integration) | Planned | Planned: entitlement integration tests | Planned: entitlement decision audit records | No premium feature should rely on hidden/implicit gating | Primary monetization operability gap |

---

## 5) Planned Enforcement Backlog

Priority sequence:

1. Implement explicit entitlement middleware/gates for API and policy surfaces.
2. Add entitlement decision logging to audit stream.
3. Add entitlement coverage to RC signoff evidence.
4. Add tier-aware API contract documentation for customer onboarding.

---

## 6) Usage Guidance

- Do not market a capability as tier-enforced unless its row is `Enforceable`.
- If capability is `Planned`, communicate expected timeline and blocker clearly.
- Revalidate this matrix on every tiering, API, or governance architecture change.
