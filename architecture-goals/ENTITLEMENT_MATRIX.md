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
- Version: `1.3.0`
- Last Reviewed: `2026-03-14`
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
- Baseline entitlement middleware for governance ingress and tenant policy overlay surfaces is `Enforceable`.
- Baseline ingress performance budget and timeout fail-safe controls are `Enforceable`.
- Full ingress governance customization depth and broader premium surface coverage remain `Planned`.

---

## 4) Feature-to-Tier Matrix

| Capability | Tier | Enforcement surface (API/config/policy) | Current state | Test evidence | Audit/evidence anchor | Non-bypass constraint | Notes / blockers |
|---|---|---|---|---|---|---|---|
| Provider-neutral adapter registration and selection | Foundation | `POST/GET/DELETE /providers*`, `src/config/provider_registry.py` | Enforceable | `tests/modules/api/test_slice_provider_registration.py`, `tests/modules/config/test_provider_registry.py` | provider health/capability endpoints evidence | Must remain contract/capability-based, not provider-name hardcoded in core | Baseline adoption capability |
| Deterministic policy-governed tool path | Foundation | `src/tools/executor.py`, `src/policies/middleware.py`, mode selection in `src/runtime/mode_selector.py` | Enforceable | `tests/modules/policies/test_policy_risk_gates.py`, `tests/modules/policies/test_deterministic_tool_replay.py`, `tests/modules/core/test_orchestrator_turn.py` | runtime events + policy outcomes in audit chain | Risky/state-changing calls cannot bypass policy + deterministic executor | Core trust baseline |
| Ingress safety gate baseline profiles (predefined) | Foundation | Ingress gate chain before orchestration (`src/api/routers/turns.py`, `src/integration/host_adapter.py`, `src/core/orchestrator.py`) | Enforceable (baseline) | `tests/modules/policies/test_ingress_gate_chain.py`, `tests/modules/api/test_slice3_playground.py`, `tests/modules/core/test_host_adapter_input_flow.py` | `turn_ingress_decision` audit events linked by correlation_id | Turns must not bypass baseline ingress safety path | Baseline trust guard for prompt/protocol safety |
| Tenant policy overlay controls | Foundation | `GET/PUT /{tenant_id}/policy`, `src/tenancy/policy_overlay.py` | Enforceable | `tests/modules/api/test_slice4_tenant_policy.py` | policy change and outcome visibility via runtime/audit APIs | Overlay must not bypass core policy middleware | Baseline governance configurability |
| Tenant quota controls | Foundation | `GET/PUT /{tenant_id}/quota`, `src/tenancy/quotas.py` | Enforceable | `tests/modules/core/test_tenant_quota_enforcement.py`, `tests/modules/api/test_slice4_tenant_policy.py` | runtime control stats and run outcomes | Quota checks remain tenant-scoped | `active_jobs` live tracking is post-v1 improvement |
| Core audit events/report access | Foundation | `GET /admin/audit/events`, `GET /admin/audit/report` | Enforceable | `tests/modules/api/test_audit_api.py` | audit report payloads | Audit collection cannot be disabled on risky paths | Baseline observability for operations |
| Advanced runtime admin controls | Pro | `src/api/routers/runtime_control.py` (`/admin/runtime/*`) | Enforceable | `tests/modules/api/test_runtime_control_api.py`, `tests/modules/api/test_byoc_runtime_control_api.py` | runtime control stats and cancellation records | Must remain authz + tenant-scoped | Pro operations depth |
| Advanced fallback/routing governance | Pro | `/{tenant_id}/agents/routes`, `/{tenant_id}/agents/fallback` | Enforceable | `tests/modules/agents/test_orchestrator_agent_handoff.py`, `tests/modules/api/test_slice2_tools_agents.py` | route/fallback behavior visible in run traces | Fallback cannot reduce deterministic safety posture | Pro orchestration control |
| BYOC governance analytics and anomaly reporting | Pro | `/{tenant_id}/admin/byoc/governance-metrics`, `src/policies/governance_anomaly_detector.py` | Enforceable | `tests/modules/policies/test_governance_anomaly_detector.py` | governance metrics endpoint payloads | Advisory analytics cannot bypass policy decisions | Pro governance insight |
| Policy templates and packaged risk profiles | Pro | Planned policy-pack API/config layer | Planned | Planned: policy-pack contract tests | Planned: policy-pack audit trail | Templates must compile to standard policy overlay/gate paths | Requires template registry and entitlement gate implementation |
| Custom declarative gate rules and protocol policies | Pro | Planned tenant gate profile API/config surfaces | Planned | Planned: custom gate evaluation tests and validation tests | Planned: per-gate allow/deny/escalate decision records | Custom rules can only tighten or specialize behavior; cannot disable trust baseline | Requires governance DSL/schema and validation runtime |
| Specialized low-cost classifier gates and shadow mode | Pro | Planned gate-chain model routing + evaluation mode controls | Planned | Planned: classifier gate tests, shadow/evaluate-only tests | Planned: score/confidence/latency telemetry in audit stream | Classifier fallback behavior must be explicit (fail-safe mode) | Requires performance budgets and model version traceability |
| Signed audit export and verification workflow | Enterprise | `POST /admin/audit/export-file`, `POST /admin/audit/verify` | Enforceable | `tests/modules/audit/test_evidence_bundle_generation.py`, `tests/modules/audit/test_audit_chain_integrity.py`, `tests/modules/api/test_audit_api.py` | signed bundle artifacts and verify responses | Signature/chain verification must remain server-side | Enterprise compliance-ready evidence |
| Signed custom gate plugins (sandboxed, compatibility-checked) | Enterprise | Planned plugin package lifecycle + sandboxed gate runner | Planned | Planned: plugin compatibility, sandbox policy, and non-bypass tests | Planned: plugin load/evaluate/unload decision evidence | No unsigned or unsandboxed gate plugin may execute in production path | Requires plugin signing, lifecycle policy, and strict runtime limits |
| Advanced fairness/admission controls | Enterprise | `src/policies/byoc_fairness.py`, runtime settings in `src/config/settings.py` | Enforceable (feature-flagged) | `tests/modules/policies/test_byoc_fairness.py`, `tests/modules/tools/test_byoc_non_blocking_execute.py` | runtime stats and governance metrics | Fairness cannot weaken tenant isolation or policy controls | Enterprise scale governance |
| Enterprise release signoff evidence bundle | Enterprise | `scripts/release/verify_gates.py`, `make rc-signoff*` | Enforceable | `tests/modules/unknown/test_release_scripts.py` | RC signoff artifacts | Release cannot skip P0 gates | Enterprise operational assurance |
| Entitlement middleware and hard API gating by tier | Cross-tier | `src/api/middleware/entitlements.py`, `src/policies/entitlements.py`, gating in `src/api/routers/turns.py` + `src/api/routers/tenants.py` | Enforceable (governance baseline) | `tests/modules/policies/test_entitlements.py`, `tests/modules/api/test_slice3_playground.py`, `tests/modules/api/test_slice4_tenant_policy.py` | `entitlement_decision` audit records on turn-ingress and tenant-policy surfaces | No premium feature should rely on hidden/implicit gating | Baseline delivered; extend to remaining premium surfaces |
| Gate performance budget and fail-safe policy controls | Cross-tier | `src/observability/ingress_budget.py`, ingress budget enforcement in `src/api/routers/turns.py`, release gate in `scripts/perf/ingress_budget_report.py` + `scripts/release/verify_gates.py` | Enforceable (baseline) | `tests/modules/observability/test_ingress_budget.py`, `tests/modules/api/test_slice3_playground.py`, `tests/modules/unknown/test_release_scripts.py` | `turn_ingress_decision`/`turn_ingress_budget_alert` audit events + `artifacts/evidence/ingress_budget_report.json` | Performance controls must not allow unsafe silent bypass | Baseline delivered; extend to full profile-specific SLOs |

---

## 5) Planned Enforcement Backlog

Priority sequence:

1. Extend entitlement middleware/gates from ingress + tenant policy baseline to all planned premium governance surfaces.
2. Add deeper tier-aware ingress profile/custom-rule APIs with schema validation and compatibility controls.
3. Add deeper profile-specific governance SLO targets and per-profile reporting.
4. Add tier-aware API contract documentation for customer onboarding.

---

## 6) Usage Guidance

- Do not market a capability as tier-enforced unless its row is `Enforceable`.
- If capability is `Planned`, communicate expected timeline and blocker clearly.
- Revalidate this matrix on every tiering, API, or governance architecture change.
