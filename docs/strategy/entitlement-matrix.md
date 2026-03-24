<!--
File: ENTITLEMENT_MATRIX.md
Path: entitlement-matrix.md
Role: Enforceable feature-to-tier entitlement mapping for monetization and enterprise packaging.
Used By:
 - monetization-strategy.md
 - deployment-models.md
 - traceability-matrix.md
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
- Version: `1.10.0`
- Last Reviewed: `2026-03-15`
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
- Baseline entitlement middleware for governance ingress, tenant policy overlays, runtime admin controls, agent routing/fallback controls, BYOC governance analytics, and signed audit export/verify surfaces is `Enforceable`.
- Baseline ingress performance budget and timeout fail-safe controls are `Enforceable`.
- Profile-specific ingress governance SLO thresholds and per-profile release evidence reporting are `Enforceable`.
- Baseline ingress profiles + custom declarative rules with compatibility validation are `Enforceable`.
- Baseline specialized ingress classifier controls (shadow/enforce + telemetry anchors) are `Enforceable`.
- Baseline signed ingress plugin lifecycle controls (load/reload/unload guards + sandbox/compatibility/signature checks) are `Enforceable`.
- Baseline policy-template and packaged-risk-profile APIs are `Enforceable` (tier-gated).
- Deeper governance customization depth (advanced external classifier model-routing depth + external signed-plugin package ingestion) remains `Planned`.

---

## 4) Feature-to-Tier Matrix

| Capability | Tier | Enforcement surface (API/config/policy) | Current state | Test evidence | Audit/evidence anchor | Non-bypass constraint | Notes / blockers |
|---|---|---|---|---|---|---|---|
| Provider-neutral adapter registration and selection | Foundation | `POST/GET/DELETE /providers*`, `src/config/provider_registry.py` | Enforceable | `tests/modules/api/test_slice_provider_registration.py`, `tests/modules/config/test_provider_registry.py` | provider health/capability endpoints evidence | Must remain contract/capability-based, not provider-name hardcoded in core | Baseline adoption capability |
| Deterministic policy-governed tool path | Foundation | `src/tools/executor.py`, `src/policies/middleware.py`, mode selection in `src/runtime/mode_selector.py` | Enforceable | `tests/modules/policies/test_policy_risk_gates.py`, `tests/modules/policies/test_deterministic_tool_replay.py`, `tests/modules/core/test_orchestrator_turn.py` | runtime events + policy outcomes in audit chain | Risky/state-changing calls cannot bypass policy + deterministic executor | Core trust baseline |
| Ingress safety gate baseline profiles (predefined) | Foundation | Ingress gate chain before orchestration (`src/api/routers/turns.py`, `src/integration/host_adapter.py`, `src/core/orchestrator.py`) + profile resolution in `src/policies/ingress_profiles.py` | Enforceable (profile-aware baseline) | `tests/modules/policies/test_ingress_gate_chain.py`, `tests/modules/policies/test_ingress_profiles.py`, `tests/modules/api/test_slice3_playground.py`, `tests/modules/core/test_host_adapter_input_flow.py` | `turn_ingress_decision` + `tenant_policy_ingress_profile_configured` audit events linked by correlation_id | Turns must not bypass baseline ingress safety path | Baseline trust guard for prompt/protocol safety |
| Tenant policy overlay controls | Foundation | `GET/PUT /{tenant_id}/policy`, `src/tenancy/policy_overlay.py` | Enforceable | `tests/modules/api/test_slice4_tenant_policy.py` | policy change and outcome visibility via runtime/audit APIs | Overlay must not bypass core policy middleware | Baseline governance configurability |
| Tenant quota controls | Foundation | `GET/PUT /{tenant_id}/quota`, `src/tenancy/quotas.py` | Enforceable | `tests/modules/core/test_tenant_quota_enforcement.py`, `tests/modules/api/test_slice4_tenant_policy.py` | runtime control stats and run outcomes | Quota checks remain tenant-scoped | `active_jobs` live tracking is post-v1 improvement |
| Core audit events/report access | Foundation | `GET /admin/audit/events`, `GET /admin/audit/report` | Enforceable | `tests/modules/api/test_audit_api.py` | audit report payloads | Audit collection cannot be disabled on risky paths | Baseline observability for operations |
| Advanced runtime admin controls | Pro | `src/api/routers/runtime_control.py` (`/admin/runtime/*`, including `/admin/runtime/ingress-budget`) with `src/api/middleware/entitlements.py` | Enforceable (tier-gated) | `tests/modules/api/test_runtime_control_api.py`, `tests/modules/api/test_byoc_runtime_control_api.py` | runtime control stats/cancellation records + ingress budget profile summaries + `entitlement_decision` audit records | Must remain authz + tenant-scoped | Pro operations depth |
| Advanced fallback/routing governance | Pro | `/{tenant_id}/agents/routes`, `/{tenant_id}/agents/fallback` with `src/api/middleware/entitlements.py` | Enforceable (tier-gated) | `tests/modules/agents/test_orchestrator_agent_handoff.py`, `tests/modules/api/test_slice2_tools_agents.py` | route/fallback behavior visible in run traces + `entitlement_decision` audit records | Fallback cannot reduce deterministic safety posture | Pro orchestration control |
| BYOC governance analytics and anomaly reporting | Pro | `/{tenant_id}/admin/byoc/governance-metrics`, `src/policies/governance_anomaly_detector.py`, entitlement checks in `src/api/routers/runtime_control.py` | Enforceable (tier-gated) | `tests/modules/policies/test_governance_anomaly_detector.py`, `tests/modules/api/test_byoc_runtime_control_api.py` | governance metrics endpoint payloads + `entitlement_decision` audit records | Advisory analytics cannot bypass policy decisions | Pro governance insight |
| Policy templates and packaged risk profiles | Pro | `GET /{tenant_id}/policy/templates`, `POST /{tenant_id}/policy/templates/{template_id}/apply`, `src/policies/policy_templates.py`, `src/api/routers/tenants.py` | Enforceable (baseline, tier-gated) | `tests/modules/policies/test_policy_templates.py`, `tests/modules/api/test_slice4_tenant_policy.py`, `tests/modules/policies/test_entitlements.py` | `tenant_policy_template_applied` + `tenant_policy_ingress_profile_configured` + `entitlement_decision` audit anchors | Templates must compile to standard policy overlay/gate paths and block locked ingress-field overrides | Baseline packaged templates + merge/replace apply modes delivered; external template publishing/certification remains planned |
| Custom declarative gate rules and protocol policies | Pro | Tenant policy API (`PUT /{tenant_id}/policy`) + ingress profile resolver (`src/policies/ingress_profiles.py`) + runtime gate evaluation (`src/policies/ingress_gates.py`) | Enforceable (baseline) | `tests/modules/policies/test_ingress_profiles.py`, `tests/modules/policies/test_ingress_gate_chain.py`, `tests/modules/api/test_slice4_tenant_policy.py`, `tests/modules/api/test_slice3_playground.py` | `tenant_policy_ingress_profile_configured` + `turn_ingress_decision` audit records | Custom rules can only tighten or specialize behavior; cannot disable trust baseline | Baseline delivered with contains/regex rule types; advanced classifier/plugin depth still planned |
| Specialized low-cost classifier gates and shadow mode | Pro | `src/policies/ingress_profiles.py` classifier config + `src/policies/ingress_gates.py` classifier gate + ingress routing in `src/api/routers/turns.py` | Enforceable (baseline, tier-gated) | `tests/modules/policies/test_ingress_profiles.py`, `tests/modules/policies/test_ingress_gate_chain.py`, `tests/modules/api/test_slice4_tenant_policy.py`, `tests/modules/api/test_slice3_playground.py` | `turn_ingress_classifier_telemetry` + `turn_ingress_decision` + `tenant_policy_ingress_profile_configured` + `entitlement_decision` audit anchors | Classifier mode (`shadow`/`enforce`) must be explicit and non-bypassable at turn ingress | Heuristic classifier baseline delivered; advanced external classifier routing remains planned |
| Signed audit export and verification workflow | Enterprise | `POST /admin/audit/export-file`, `POST /admin/audit/verify` with entitlement checks in `src/api/routers/audit.py` | Enforceable (tier-gated) | `tests/modules/audit/test_evidence_bundle_generation.py`, `tests/modules/audit/test_audit_chain_integrity.py`, `tests/modules/api/test_audit_api.py` | signed bundle artifacts and verify responses + `entitlement_decision` audit records | Signature/chain verification must remain server-side | Enterprise compliance-ready evidence |
| Signed custom gate plugins (sandboxed, compatibility-checked) | Enterprise | Signed plugin resolution + lifecycle guards in `src/policies/ingress_signed_plugins.py`, tenant overlay lifecycle enforcement in `src/api/routers/tenants.py`, gate execution in `src/policies/ingress_gates.py` | Enforceable (baseline, tier-gated) | `tests/modules/policies/test_ingress_signed_plugins.py`, `tests/modules/policies/test_ingress_profiles.py`, `tests/modules/policies/test_ingress_gate_chain.py`, `tests/modules/api/test_slice4_tenant_policy.py`, `tests/modules/api/test_slice3_playground.py` | `tenant_policy_signed_gate_plugin_lifecycle` + `turn_ingress_signed_plugin_telemetry` + `turn_ingress_decision` + `entitlement_decision` audit anchors | No unsigned, untrusted-signer, incompatible-core, or non-declarative plugin may execute in ingress path | Baseline delivered with trusted in-repo signed registry and declarative sandbox policy; external plugin package ingestion remains planned |
| Advanced fairness/admission controls | Enterprise | `src/policies/byoc_fairness.py`, runtime settings in `src/config/settings.py` | Enforceable (feature-flagged) | `tests/modules/policies/test_byoc_fairness.py`, `tests/modules/tools/test_byoc_non_blocking_execute.py` | runtime stats and governance metrics | Fairness cannot weaken tenant isolation or policy controls | Enterprise scale governance |
| Enterprise release signoff evidence bundle | Enterprise | `scripts/release/verify_gates.py`, `make rc-signoff*` | Enforceable | `tests/modules/release_scripts/test_release_scripts.py` | RC signoff artifacts | Release cannot skip P0 gates | Enterprise operational assurance |
| Entitlement middleware and hard API gating by tier | Cross-tier | `src/api/middleware/entitlements.py`, `src/policies/entitlements.py`, gating in `src/api/routers/turns.py`, `src/api/routers/tenants.py`, `src/api/routers/runtime_control.py`, `src/api/routers/agents.py`, and `src/api/routers/audit.py` | Enforceable (expanded governance surfaces) | `tests/modules/policies/test_entitlements.py`, `tests/modules/api/test_slice3_playground.py`, `tests/modules/api/test_slice4_tenant_policy.py`, `tests/modules/api/test_runtime_control_api.py`, `tests/modules/api/test_byoc_runtime_control_api.py`, `tests/modules/api/test_slice2_tools_agents.py`, `tests/modules/api/test_audit_api.py` | `entitlement_decision` audit records on ingress, policy, runtime admin, routing/fallback, BYOC analytics, and signed-audit surfaces | No premium feature should rely on hidden/implicit gating | Expanded baseline delivered; remaining work is planned premium capability build-out |
| Gate performance budget and fail-safe policy controls | Cross-tier | `src/observability/ingress_budget.py`, ingress budget enforcement in `src/api/routers/turns.py`, runtime profile reporting in `src/api/routers/runtime_control.py` (`GET /{tenant_id}/admin/runtime/ingress-budget`), release gate in `scripts/perf/ingress_budget_report.py` + `configs/release/ingress_budget_thresholds.json` + `scripts/release/verify_gates.py` | Enforceable (profile-aware baseline) | `tests/modules/observability/test_ingress_budget.py`, `tests/modules/api/test_slice3_playground.py`, `tests/modules/api/test_runtime_control_api.py`, `tests/modules/perf_scripts/test_ingress_budget_report.py`, `tests/modules/release_scripts/test_release_scripts.py` | `turn_ingress_decision`/`turn_ingress_budget_alert` audit events + runtime ingress budget summary endpoint + `artifacts/evidence/ingress_budget_report.json` | Performance controls must not allow unsafe silent bypass | Profile-specific thresholds + per-profile runtime/release reporting delivered; continue deep runtime diagnostics over time |

---

## 5) Planned Enforcement Backlog

Priority sequence:

1. Add tier-aware API contract documentation for customer onboarding.
2. Add advanced external classifier model-routing controls with explicit fallback and evidence anchors.
3. Add external signed-plugin package ingestion workflow with publisher trust onboarding and certification evidence.
4. Add first-class human approval lifecycle controls for escalated/review-required decisions (approve/reject APIs, actor attribution, and audit-linked state transitions).

---

## 6) Usage Guidance

- Do not market a capability as tier-enforced unless its row is `Enforceable`.
- If capability is `Planned`, communicate expected timeline and blocker clearly.
- Revalidate this matrix on every tiering, API, or governance architecture change.
