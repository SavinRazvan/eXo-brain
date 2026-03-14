<!--
File: TRACEABILITY_MATRIX.md
Path: architecture-goals/TRACEABILITY_MATRIX.md
Role: Strategy-to-implementation traceability map for architecture, governance, and monetization decisions.
Used By:
 - architecture-goals/GOAL.md
 - architecture-goals/CORE.md
 - architecture-goals/ADAPTER_STRATEGY.md
 - architecture-goals/MONETIZATION_STRATEGY.md
 - architecture-goals/ENTITLEMENT_MATRIX.md
 - architecture-goals/COMPLIANCE_PROFILE_MATRIX.md
 - architecture-goals/DEPLOYMENT_MODELS.md
 - architecture-goals/INTERFACE_STRATEGY.md
Depends On:
 - src/*
 - tests/modules/*
 - tests/packages/*
 - scripts/architecture/*
 - scripts/release/*
Notes:
 - Update this matrix when strategic decisions or implementation anchors change.
-->

# Traceability Matrix

## Governance Metadata

- Status: `active`
- Owner: `Savin I. Razvan`
- Version: `1.9.0`
- Last Reviewed: `2026-03-14`
- Review Cadence: `monthly`
- Decision Scope: `Cross-document mapping from strategy decisions to code, API, tests, and release evidence anchors.`

## 1) Purpose

This matrix prevents strategy drift by mapping each major decision to:
- code anchors,
- API/control surfaces,
- tests,
- release/architecture gates.

If a strategic decision has no active code/test anchor, it is considered at risk.

---

## 2) Strategic Decision -> Implementation Mapping

| Strategic area | Decision | Code anchors | API / control anchors | Test anchors | Gate / evidence anchors |
|---|---|---|---|---|---|
| Core boundaries | Core remains provider-neutral | `src/core/orchestrator.py`, `src/runtime/runtime_adapter.py`, `src/runtime/mode_selector.py` | N/A (internal architecture) | `tests/modules/runtime/test_mode_selector.py`, `tests/modules/core/test_multi_adapter_workflow_parity.py` | `scripts/architecture/validate_layers.py`, `scripts/architecture/scan_forbidden_imports.py` |
| Deterministic safety | Risky/state-changing calls must use deterministic execution | `src/tools/executor.py`, `src/policies/middleware.py`, `src/policies/risk_gates.py` | `src/api/routers/turns.py` streaming execution path | `tests/modules/policies/test_policy_risk_gates.py`, `tests/modules/policies/test_deterministic_tool_replay.py`, `tests/modules/core/test_orchestrator_turn.py` | RC signoff via `scripts/release/verify_gates.py` |
| Policy non-bypass | Policy must run before/after side effects | `src/policies/middleware.py`, `src/tools/decorators.py` | tenant policy overlay endpoints in `src/api/routers/tenants.py` | `tests/modules/policies/test_plugins_and_decorators.py`, `tests/modules/api/test_slice4_tenant_policy.py` | Release candidate signoff checklist and policy test suites |
| Ingress safety governance | Turn requests must receive pre-model allow/deny/escalate decisions with reason codes and audit continuity | `src/api/routers/turns.py`, `src/policies/ingress_gates.py`, `src/policies/ingress_profiles.py`, `src/policies/ingress_signed_plugins.py`, `src/integration/host_adapter.py`, `src/core/orchestrator.py` | turn execution endpoints (SSE/WS) plus tenant ingress profile/classifier/signed-plugin policy controls | `tests/modules/api/test_slice3_playground.py`, `tests/modules/policies/test_ingress_gate_chain.py`, `tests/modules/policies/test_ingress_profiles.py`, `tests/modules/policies/test_ingress_signed_plugins.py`, `tests/modules/core/test_host_adapter_input_flow.py` | `src/observability/tool_audit.py` (`turn_ingress_decision`, `turn_ingress_classifier_telemetry`, `turn_ingress_signed_plugin_telemetry`) + release gates |
| Tenant isolation | Isolation across tools/agents/sessions/policies | `src/runtime/tenant_runtime.py`, `src/tenancy/*`, `src/core/session_store.py` | `src/api/routers/tenants.py`, tenant-scoped routes across routers | `tests/modules/runtime/test_tenant_runtime.py`, `tests/modules/persistence/test_cross_tenant_isolation.py` | Architecture checks + tenant API tests in CI |
| Quota/fairness governance | Bounded admission and fairness controls | `src/tenancy/quotas.py`, `src/tenancy/rate_limiter.py`, `src/policies/byoc_fairness.py`, `src/core/run_control_registry.py` | runtime admin control endpoints in `src/api/routers/runtime_control.py` | `tests/modules/core/test_tenant_quota_enforcement.py`, `tests/modules/policies/test_byoc_fairness.py` | `scripts/release/verify_gates.py`, Option C threshold config |
| Audit integrity | Auditable, verifiable evidence for runtime actions | `src/audit/*`, `src/persistence/*audit*` | `src/api/routers/audit.py` | `tests/modules/audit/test_audit_chain_integrity.py`, `tests/modules/audit/test_evidence_bundle_generation.py`, `tests/modules/api/test_audit_api.py` | RC signoff artifacts + audit export/verify checks |
| API-first interface | Platform works without required UI | `src/api/app.py`, `src/api/routers/*` | REST/SSE/WS endpoints in API routers | `tests/modules/api/test_slice1_transport.py`, `tests/modules/api/test_slice3_playground.py`, `tests/modules/api/test_ui_static.py` | API release signoff and architecture checks |
| Adapter packaging split | Core contracts + adapter SDK + provider adapters | `packages/exo-brain-core-contracts/*`, `packages/exo-brain-adapter-sdk/*`, `packages/exo-adapter-openai/*`, `src/runtime/adapter_factory.py` | provider registration in `src/api/routers/providers.py` + startup hydration in `src/api/startup.py` | `tests/packages/test_core_contracts_imports.py`, `tests/packages/test_openai_adapter_conformance.py`, `tests/modules/runtime/test_adapter_factory.py` | `scripts/architecture/scan_forbidden_imports.py` (adapter-package monorepo-import guard) + package conformance tests in CI |
| Provider registration and portability | Provider adapters registered by contract/capability | `src/config/provider_registry.py`, runtime adapter modules | `src/api/routers/providers.py` | `tests/modules/config/test_provider_registry.py`, `tests/modules/api/test_slice_provider_registration.py` | Architecture checks + provider API tests |
| Agent routing and fallback | Fallback and handoff are configurable and governed | `src/agents/registry.py`, `src/agents/contracts.py` | `src/api/routers/agents.py` (`routes` and `fallback`) | `tests/modules/agents/test_agent_registry.py`, `tests/modules/agents/test_orchestrator_agent_handoff.py`, `tests/modules/api/test_slice2_tools_agents.py` | CI integration suites |
| Runtime observability | Runtime behavior must be observable and diagnosable | `src/observability/logging.py`, `src/observability/metrics.py`, `src/observability/tracing.py`, `src/observability/timeline.py` | runtime stats endpoints in `src/api/routers/runtime_control.py` | `tests/modules/observability/test_observability.py`, `tests/modules/observability/test_release_guardrails.py`, `tests/modules/core/test_scheduler_observability.py` | RC signoff evidence + observability test suites |
| Governance customization depth | Customers can use predefined/custom governance controls, classifier shadow/enforce modes, and signed plugin lifecycle controls under explicit entitlement boundaries | `src/tenancy/policy_overlay.py`, `src/api/routers/tenants.py`, `src/policies/ingress_profiles.py`, `src/policies/ingress_gates.py`, `src/policies/ingress_signed_plugins.py` | tenant policy APIs with profile/custom-rule/classifier/signed-plugin schema validation + compatibility controls | `tests/modules/api/test_slice4_tenant_policy.py`, `tests/modules/api/test_slice3_playground.py`, `tests/modules/policies/test_ingress_profiles.py`, `tests/modules/policies/test_ingress_gate_chain.py`, `tests/modules/policies/test_ingress_signed_plugins.py` | `architecture-goals/ENTITLEMENT_MATRIX.md`, `tenant_policy_ingress_profile_configured` + `tenant_policy_signed_gate_plugin_lifecycle` + `turn_ingress_decision` + `turn_ingress_classifier_telemetry` + `turn_ingress_signed_plugin_telemetry` audit anchors |
| Governance performance guarantees | Governance controls must preserve p95 turn latency and explicit fail-safe behavior | `src/api/routers/turns.py`, `src/observability/ingress_budget.py`, `scripts/perf/ingress_budget_report.py` | turn ingress surfaces enforce budget+timeout controls; release gate exports ingress budget evidence JSON | `tests/modules/observability/test_ingress_budget.py`, `tests/modules/api/test_slice3_playground.py`, `tests/modules/unknown/test_release_scripts.py` | `scripts/release/verify_gates.py` + `artifacts/evidence/ingress_budget_report.json` |
| Security posture | Secrets redaction and secure auth boundaries | `src/observability/logging.py`, `src/api/middleware/auth.py`, `src/access_control/*`, `src/secrets/*` | `src/api/routers/admin_keys.py`, auth-protected API paths | `tests/modules/observability/test_secrets_redaction.py`, `tests/modules/api/test_auth_jwt.py`, `tests/modules/api/test_auth_apikey.py`, `tests/modules/access_control/test_access_control_*` | Security and architecture test gates |
| Reliability path | Retry/cancel/resume and resilience behavior | `src/core/background_runtime.py`, `src/core/scheduler.py`, `src/resilience/*` | runtime cancellation endpoints in `src/api/routers/runtime_control.py` | `tests/modules/core/test_background_runtime_cancel_resume.py`, `tests/modules/resilience/test_retry_idempotency_guards.py`, `tests/modules/resilience/test_dlq_routing.py` | RC signoff and resilience suites |
| Monetization boundary | Premium value in governance/reliability, not adapter lock-in | governance modules in `src/policies/*`, `src/audit/*`, `src/tenancy/*` | policy/quota/runtime/audit API surfaces | usage and behavior tests across API/policy/audit modules | Strategic docs + entitlement implementation checks (to be expanded) |
| Entitlement operability | Tier claims must map to explicit enforceable controls | `src/api/middleware/entitlements.py`, `src/policies/entitlements.py`, `src/api/routers/turns.py`, `src/api/routers/tenants.py`, `src/api/routers/runtime_control.py`, `src/api/routers/agents.py`, `src/api/routers/audit.py` | tier-sensitive governance ingress + policy + runtime admin + routing/fallback + BYOC governance analytics + signed audit export/verify surfaces are hard-gated and audited | `tests/modules/policies/test_entitlements.py`, `tests/modules/api/test_slice3_playground.py`, `tests/modules/api/test_slice4_tenant_policy.py`, `tests/modules/api/test_runtime_control_api.py`, `tests/modules/api/test_byoc_runtime_control_api.py`, `tests/modules/api/test_slice2_tools_agents.py`, `tests/modules/api/test_audit_api.py` | `architecture-goals/ENTITLEMENT_MATRIX.md`, `entitlement_decision` audit events, RC signoff (remaining planned work is premium capability build-out depth) |
| Compliance profile readiness | Compliance claims must map to controls and evidence by wave | auth/policy/audit/tenancy/runtime control modules (`src/api/*`, `src/policies/*`, `src/audit/*`, `src/tenancy/*`) | compliance-facing runtime and audit APIs (`src/api/routers/audit.py`, `src/api/routers/runtime_control.py`) | auth/audit/tenant isolation/reliability suites | `architecture-goals/COMPLIANCE_PROFILE_MATRIX.md`, release evidence and audit export/verify artifacts |
| Deployment model governance | Deployment offerings must have explicit support and responsibility boundaries | control-plane + runtime governance modules (`src/api/*`, `src/runtime/*`, `src/tenancy/*`) | deployment model boundaries documented in `architecture-goals/DEPLOYMENT_MODELS.md` | transport/runtime/control API suites (deployment-sensitive behavior) | `architecture-goals/DEPLOYMENT_MODELS.md`, RC signoff + operations runbooks |

---

## 3) Current Known Gaps

| Gap | Why it matters | Current status |
|---|---|---|
| Full external adapter portability | Enables independent adapter distribution and partner ecosystem | OpenAI portability baseline completed in-repo (self-contained package runtime/tool wiring, canonical class refs, compatibility aliases, guardrails + smoke tests); next gap is external clean-project install/publish certification automation |
| Explicit entitlement hard-gating layer | Needed for clean monetization boundary by tier | Expanded baseline implemented for ingress, tenant policy overlays, runtime admin, routing/fallback, BYOC governance analytics, and signed audit export/verify; remaining planned work is premium capability build-out depth |
| Ingress governance plane with predefined + custom gates | Needed for pre-model safety, customer-governed protocols, and monetizable safety depth | Baseline implemented for turn-entry gate chain + profile/custom-rule/classifier controls + signed plugin lifecycle controls (load/reload/unload guards with declarative sandbox policy); advanced external classifier-routing depth remains planned |
| Governance performance SLO and failure-mode controls | Needed so safety depth does not degrade customer UX and reliability posture | Baseline implemented for ingress latency budget/timeout fail-safe + release evidence hook; profile-specific SLO depth remains planned |
| Canonical UI roadmap contract | Needed to avoid future UI-vs-API drift | Deferred by design under API-first posture; strategy documented in `INTERFACE_STRATEGY.md` |
| Private/self-hosted deployment certification model | Needed before strict enterprise self-hosted support claims | Planned; documented as deferred in `DEPLOYMENT_MODELS.md` pending maturity gates |

---

## 4) Drift Detection Workflow

Use this workflow on architecture-impacting changes:

1. Update strategic decision docs in `architecture-goals/`.
2. Update this matrix with code/API/test anchors.
3. Run tests and architecture gates.
4. Verify RC signoff artifacts remain healthy.
5. Capture any accepted divergence with rationale and owner.

---

## 5) Update Checklist

- Are all new strategic decisions represented in this matrix?
- Does each decision map to at least one code anchor and one test anchor?
- Are API control points documented where customer configuration is expected?
- Are gate/evidence anchors still valid and executable?

If any answer is "no", documentation is incomplete.
