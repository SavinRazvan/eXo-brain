<!--
File: traceability-matrix.md
Path: traceability-matrix.md
Role: Strategy-to-implementation traceability map for architecture, governance, and monetization decisions.
Used By:
 - goal.md
 - core.md
 - adapter-strategy.md
 - monetization-strategy.md
 - entitlement-matrix.md
 - compliance-profile-matrix.md
 - deployment-models.md
 - interface-strategy.md
 - execution-board-12-gaps.md
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
- Version: `1.17.0`
- Last Reviewed: `2026-03-15`
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
| Ingress safety governance | Turn requests must receive pre-model allow/deny/escalate decisions with reason codes and audit continuity | `src/api/routers/turns.py`, `src/policies/ingress_gates.py`, `src/policies/ingress_profiles.py`, `src/policies/ingress_signed_plugins.py`, `src/policies/ingress_classifier_router.py`, `src/integration/host_adapter.py`, `src/core/orchestrator.py` | turn execution endpoints (SSE/WS) plus tenant ingress profile/classifier/signed-plugin policy controls | `tests/modules/api/test_slice3_playground.py`, `tests/modules/policies/test_ingress_gate_chain.py`, `tests/modules/policies/test_ingress_profiles.py`, `tests/modules/policies/test_ingress_signed_plugins.py`, `tests/modules/policies/test_external_classifier_routing.py`, `tests/modules/core/test_host_adapter_input_flow.py` | `src/observability/tool_audit.py` (`turn_ingress_decision`, `turn_ingress_classifier_telemetry`, `turn_ingress_signed_plugin_telemetry`) + release gates |
| Tenant isolation | Isolation across tools/agents/sessions/policies | `src/runtime/tenant_runtime.py`, `src/tenancy/*`, `src/core/session_store.py` | `src/api/routers/tenants.py`, tenant-scoped routes across routers | `tests/modules/runtime/test_tenant_runtime.py`, `tests/modules/persistence/test_cross_tenant_isolation.py` | Architecture checks + tenant API tests in CI |
| Quota/fairness governance | Bounded admission and fairness controls | `src/tenancy/quotas.py`, `src/tenancy/rate_limiter.py`, `src/policies/byoc_fairness.py`, `src/core/run_control_registry.py` | runtime admin control endpoints in `src/api/routers/runtime_control.py` | `tests/modules/core/test_tenant_quota_enforcement.py`, `tests/modules/policies/test_byoc_fairness.py` | `scripts/release/verify_gates.py`, Option C threshold config |
| Audit integrity | Auditable, verifiable evidence for runtime actions | `src/audit/*`, `src/persistence/*audit*` | `src/api/routers/audit.py` | `tests/modules/audit/test_audit_chain_integrity.py`, `tests/modules/audit/test_evidence_bundle_generation.py`, `tests/modules/api/test_audit_api.py` | RC signoff artifacts + audit export/verify checks |
| API-first interface | Platform works without required UI | `src/api/app.py`, `src/api/routers/*` | REST/SSE/WS endpoints in API routers | `tests/modules/api/test_slice1_transport.py`, `tests/modules/api/test_slice3_playground.py`, `tests/modules/api/test_ui_static.py` | API release signoff and architecture checks |
| Adapter packaging split | Core contracts + adapter SDK + provider adapters | `packages/exo-brain-core-contracts/*`, `packages/exo-brain-adapter-sdk/*`, `packages/exo-adapter-openai/*`, `src/runtime/adapter_factory.py` | provider registration in `src/api/routers/providers.py` + startup hydration in `src/api/startup.py` | `tests/packages/test_core_contracts_imports.py`, `tests/packages/test_openai_adapter_conformance.py`, `tests/modules/runtime/test_adapter_factory.py` | `scripts/architecture/scan_forbidden_imports.py` (adapter-package monorepo-import guard) + `scripts/packages/external_install_smoke.py` (isolated-venv external install certification) + package conformance tests in CI |
| Provider registration and portability | Provider adapters registered by contract/capability | `src/config/provider_registry.py`, runtime adapter modules | `src/api/routers/providers.py` | `tests/modules/config/test_provider_registry.py`, `tests/modules/api/test_slice_provider_registration.py` | Architecture checks + provider API tests |
| Provider protocol explicitness | Provider registration must carry endpoint protocol type (`openai_native`, `openai_compatible`, `custom`) rather than rely on implicit defaults | `src/api/schemas/provider_schemas.py`, `src/api/routers/providers.py`, `src/config/provider_registry.py` | `POST /providers` request schema and provider persistence model | provider registration contract tests + registry tests (expand current suites) | architecture checks + provider API conformance gates |
| Adapter portfolio expansion v2 | Use three-lane expansion model (universal compatible, native adapter, service/tool lane) to onboard providers without breaking core boundaries | `packages/exo-brain-adapter-sdk/*`, `packages/exo-adapter-openai/*`, planned universal-compatible adapter package, planned native adapter packages, `src/runtime/adapter_factory.py`, `src/tools/*` for service lane | provider registration/listing/capability surfaces + tenant routing/fallback/policy controls | adapter conformance suites + cross-adapter parity/fallback suites + service-tool policy/audit suites (planned expansion) | external install smoke + architecture checks + release certification evidence per provider |
| Runtime provider routing depth | Gateway-grade provider selection should be health/cost/policy aware with transparent fallback and safety non-regression | `src/config/provider_registry.py`, `src/runtime/adapter_factory.py`, planned provider router module(s) in `src/runtime/*` | turn/runtime provider selection controls + routing telemetry surfaces | provider routing/failover parity tests + safety non-regression tests (planned expansion) | release evidence includes per-turn routing decision traces |
| Agent routing and fallback | Fallback and handoff are configurable and governed | `src/agents/registry.py`, `src/agents/contracts.py` | `src/api/routers/agents.py` (`routes` and `fallback`) | `tests/modules/agents/test_agent_registry.py`, `tests/modules/agents/test_orchestrator_agent_handoff.py`, `tests/modules/api/test_slice2_tools_agents.py` | CI integration suites |
| Runtime observability | Runtime behavior must be observable and diagnosable | `src/observability/logging.py`, `src/observability/metrics.py`, `src/observability/tracing.py`, `src/observability/timeline.py` | runtime stats endpoints in `src/api/routers/runtime_control.py` | `tests/modules/observability/test_observability.py`, `tests/modules/observability/test_release_guardrails.py`, `tests/modules/core/test_scheduler_observability.py` | RC signoff evidence + observability test suites |
| Human approval workflow surface | Escalated/review-required decisions should support explicit approve/reject lifecycle transitions with audit continuity | `src/policies/risk_gates.py`, `src/policies/ingress_gates.py`, planned approval workflow modules/routes | planned approval action APIs (admin/tenant-governed) + turn review status linkage | approval lifecycle, authz, and audit chain tests (planned) | entitlement and audit export/verify evidence anchors (planned) |
| Enterprise telemetry export interoperability | Add first-class OTel/Prometheus-compatible telemetry export path without regressing deterministic diagnostics | `src/observability/logging.py`, `src/observability/metrics.py`, `src/observability/tracing.py`, planned exporter modules | runtime observability controls + release evidence outputs | observability integration tests + release guardrail tests (planned expansion) | RC signoff evidence includes exporter health/coverage checks |
| External classifier wiring depth | External classifier contract should be injected from tenant/runtime config into ingress gate execution, with fallback evidence | `src/policies/ingress_classifier_router.py`, `src/policies/ingress_gates.py`, `src/policies/ingress_profiles.py`, `src/api/routers/turns.py` | ingress policy/profile APIs + classifier routing controls | classifier integration and timeout/fallback tests (planned expansion) | classifier decision telemetry + release evidence |
| Signed plugin ingestion depth | Move from registry-static signed plugins to controlled external package ingestion and trust lifecycle operations | `src/policies/ingress_signed_plugins.py`, `src/api/routers/tenants.py`, planned plugin ingestion modules | tenant policy APIs + signed plugin lifecycle controls | plugin ingestion/signature/compatibility/rollback tests (planned expansion) | signed plugin lifecycle audit anchors + entitlement evidence |
| MCP policy depth | MCP governance should include per-server tool allow/deny filters and scoped credential policy enforcement beyond trust-tier/health state | `src/mcp/mcp_registry.py`, `src/mcp/mcp_tool_adapter.py`, planned MCP policy modules | MCP server registration/policy control surfaces | MCP policy enforcement tests + audit assertions (planned expansion) | MCP policy decision evidence in runtime/audit telemetry |
| Token-aware inference governance | Add token/cost-aware budget and throttling actions (`allow|deny|escalate|reroute`) at inference edge | `src/tenancy/rate_limiter.py`, `src/tenancy/quotas.py`, planned token budget governance modules | tenant/admin budget controls and runtime policy surfaces | token budget threshold and policy-action tests (planned expansion) | budget decision audit events + runtime governance metrics |
| Governance customization depth | Customers can use predefined/custom governance controls, packaged risk-profile templates, classifier shadow/enforce modes, and signed plugin lifecycle controls under explicit entitlement boundaries | `src/tenancy/policy_overlay.py`, `src/api/routers/tenants.py`, `src/policies/ingress_profiles.py`, `src/policies/ingress_gates.py`, `src/policies/ingress_signed_plugins.py`, `src/policies/policy_templates.py` | tenant policy APIs with template-catalog/apply plus profile/custom-rule/classifier/signed-plugin schema validation and compatibility controls | `tests/modules/api/test_slice4_tenant_policy.py`, `tests/modules/api/test_slice3_playground.py`, `tests/modules/policies/test_ingress_profiles.py`, `tests/modules/policies/test_ingress_gate_chain.py`, `tests/modules/policies/test_ingress_signed_plugins.py`, `tests/modules/policies/test_policy_templates.py` | `entitlement-matrix.md`, `tenant_policy_template_applied` + `tenant_policy_ingress_profile_configured` + `tenant_policy_signed_gate_plugin_lifecycle` + `turn_ingress_decision` + `turn_ingress_classifier_telemetry` + `turn_ingress_signed_plugin_telemetry` + `entitlement_decision` audit anchors |
| Governance performance guarantees | Governance controls must preserve p95 turn latency and explicit fail-safe behavior | `src/api/routers/turns.py`, `src/api/routers/runtime_control.py`, `src/observability/ingress_budget.py`, `scripts/perf/ingress_budget_report.py`, `configs/release/ingress_budget_thresholds.json` | turn ingress surfaces enforce budget+timeout controls with ingress-profile tagging; runtime admin exposes per-profile ingress budget summaries; release gate exports overall + per-profile ingress budget evidence JSON | `tests/modules/observability/test_ingress_budget.py`, `tests/modules/api/test_slice3_playground.py`, `tests/modules/api/test_runtime_control_api.py`, `tests/modules/unknown/test_ingress_budget_report.py`, `tests/modules/unknown/test_release_scripts.py` | `scripts/release/verify_gates.py` + `artifacts/evidence/ingress_budget_report.json` |
| Security posture | Secrets redaction and secure auth boundaries | `src/observability/logging.py`, `src/api/middleware/auth.py`, `src/access_control/*`, `src/secrets/*` | `src/api/routers/admin_keys.py`, auth-protected API paths | `tests/modules/observability/test_secrets_redaction.py`, `tests/modules/api/test_auth_jwt.py`, `tests/modules/api/test_auth_apikey.py`, `tests/modules/access_control/test_access_control_*` | Security and architecture test gates |
| Reliability path | Retry/cancel/resume and resilience behavior | `src/core/background_runtime.py`, `src/core/scheduler.py`, `src/resilience/*` | runtime cancellation endpoints in `src/api/routers/runtime_control.py` | `tests/modules/core/test_background_runtime_cancel_resume.py`, `tests/modules/resilience/test_retry_idempotency_guards.py`, `tests/modules/resilience/test_dlq_routing.py` | RC signoff and resilience suites |
| Monetization boundary | Premium value in governance/reliability, not adapter lock-in | governance modules in `src/policies/*`, `src/audit/*`, `src/tenancy/*` | policy/quota/runtime/audit API surfaces | usage and behavior tests across API/policy/audit modules | Strategic docs + entitlement implementation checks (to be expanded) |
| Customer API surface parity | Customers need explicit integration paths covering all tiers and governance surfaces | `src/api/routers/turns.py`, `src/api/routers/tenants.py`, `src/api/routers/runtime_control.py`, `src/api/routers/agents.py`, `src/api/routers/tools.py`, `src/api/routers/audit.py`, `src/api/routers/providers.py` | all REST/SSE/WS endpoints in API routers | API and policy test suites | `docs/api/customer-api-integration-guide.md` — tier-aware contract reference covering Foundation/Pro/Enterprise surfaces, ingress profiles, audit events, safety invariants, and quickstart |
| Entitlement operability | Tier claims must map to explicit enforceable controls | `src/api/middleware/entitlements.py`, `src/policies/entitlements.py`, `src/api/routers/turns.py`, `src/api/routers/tenants.py`, `src/api/routers/runtime_control.py`, `src/api/routers/agents.py`, `src/api/routers/audit.py` | tier-sensitive governance ingress + policy + runtime admin + routing/fallback + BYOC governance analytics + signed audit export/verify surfaces are hard-gated and audited | `tests/modules/policies/test_entitlements.py`, `tests/modules/api/test_slice3_playground.py`, `tests/modules/api/test_slice4_tenant_policy.py`, `tests/modules/api/test_runtime_control_api.py`, `tests/modules/api/test_byoc_runtime_control_api.py`, `tests/modules/api/test_slice2_tools_agents.py`, `tests/modules/api/test_audit_api.py` | `entitlement-matrix.md`, `entitlement_decision` audit events, RC signoff (remaining planned work is premium capability build-out depth) |
| Compliance profile readiness | Compliance claims must map to controls and evidence by wave | auth/policy/audit/tenancy/runtime control modules (`src/api/*`, `src/policies/*`, `src/audit/*`, `src/tenancy/*`) | compliance-facing runtime and audit APIs (`src/api/routers/audit.py`, `src/api/routers/runtime_control.py`) | auth/audit/tenant isolation/reliability suites | `compliance-profile-matrix.md`, release evidence and audit export/verify artifacts |
| Deployment model governance | Deployment offerings must have explicit support and responsibility boundaries | control-plane + runtime governance modules (`src/api/*`, `src/runtime/*`, `src/tenancy/*`) | deployment model boundaries documented in `deployment-models.md` | transport/runtime/control API suites (deployment-sensitive behavior) | `deployment-models.md`, RC signoff + operations runbooks |

---

## 3) Current Known Gaps

| Gap | Why it matters | Current status |
|---|---|---|
| Full external adapter portability | Enables independent adapter distribution and partner ecosystem | External install certification complete: all three packages (`exo-brain-core-contracts`, `exo-brain-adapter-sdk`, `exo-adapter-openai`) install cleanly in an isolated venv with zero monorepo-relative imports; isolated-venv conformance smoke at `scripts/packages/external_install_smoke.py`; SDK `pyproject.toml` now declares `exo-brain-core-contracts` as a direct pip dependency; next gap is publish certification automation (PyPI upload + version tagging) |
| Provider registration protocol explicitness | Adapter portfolio expansion requires explicit protocol typing and validation, not implicit `openai_native` assumptions | Planned: add `api_type` to provider registration schemas/routes with backward-compatible fallback and persistence alignment |
| Universal adapter portfolio expansion execution | New provider list needs lane-specific implementation sequencing and safety-preserving certification gates | Planned in `adapter-strategy.md` §19 with phased milestones (M0-M5) and per-lane safety constraints |
| Runtime provider router depth | Current provider fallback posture is not yet a first-class health/cost/policy-aware routing plane | Planned: add routing module with deterministic safety non-regression guarantees and routing decision telemetry |
| Explicit entitlement hard-gating layer | Needed for clean monetization boundary by tier | Expanded baseline implemented for ingress, tenant policy overlays, runtime admin, routing/fallback, BYOC governance analytics, and signed audit export/verify; remaining planned work is premium capability build-out depth |
| Advanced entitlement depth completion | External classifier routing depth and external signed-plugin package ingestion remain partially planned | Planned backlog remains in `entitlement-matrix.md` §5; enforceable baseline exists but advanced depth still pending |
| External classifier runtime wiring depth | External classifier contract exists, but end-to-end injection and production routing evidence depth remain incomplete | Planned: wire classifier adapter selection/injection from tenant/runtime config and add timeout/fallback evidence tests |
| Signed plugin ingestion depth beyond static registry | Baseline signed plugin lifecycle is implemented, but external package ingestion and publisher trust lifecycle are still pending | Planned: add external package ingestion workflow with trust onboarding, compatibility gates, and rollback controls |
| First-class approval action workflow | `review_required`/escalation signaling exists, but explicit approve/reject action APIs are not yet mapped end-to-end | Planned: add approval lifecycle APIs, policy state transitions, and audit-linked evidence anchors |
| Ingress governance plane with predefined + custom gates | Needed for pre-model safety, customer-governed protocols, and monetizable safety depth | Implemented: turn-entry gate chain + profile/custom-rule/classifier controls + signed plugin lifecycle controls + packaged policy-template/risk-profile APIs + external classifier model-routing with transparent heuristic fallback and evidence anchors (`ExternalClassifierAdapter` contract, `ExternalClassifierRoutingGate`, routing evidence in `IngressDecision`) |
| Governance performance SLO and failure-mode controls | Needed so safety depth does not degrade customer UX and reliability posture | Profile-aware baseline implemented for ingress latency budget/timeout fail-safe + per-profile SLO thresholds + release evidence reporting; deeper runtime-control diagnostics remain planned |
| OTel/Prometheus interoperability path | Enterprise operations often require standard telemetry sinks in addition to local JSONL/in-memory diagnostics | Planned: add exporter modules, integration tests, and release evidence checks for telemetry interoperability |
| Token/cost governance at inference edge | Request-level limits exist, but token-aware budgets and policy actions are still incomplete for gateway-style spend governance | Planned: add token budget controls with deny/escalate/reroute actions and auditable threshold evidence |
| MCP governance depth (tool filters + credential policy) | Trust-tier + health posture exists, but per-server tool filtering and credential-scope policy surfaces are not yet explicit | Planned: add MCP allow/deny controls, scoped credential policy, and policy decision telemetry anchors |
| Customer-facing API contract documentation | Needed for customer onboarding across chat/agents/workflow and governance ingress surfaces | Tier-aware integration guide delivered at `docs/api/customer-api-integration-guide.md` covering all Foundation/Pro/Enterprise surfaces, ingress profiles, audit events, and integration quickstart |
| OpenAI-compatible runtime transport parity | Adapter advertises OpenAI-compatible capability but current runtime path remains lightweight echo behavior | Planned: implement full transport/auth/error/streaming parity path and map conformance tests before production claims |
| Compliance profile packaging depth | Compliance matrix indicates remaining gaps in control narratives and assessor-ready operational packaging | Planned: codify SOC2/GDPR narratives and HIPAA/PCI/public-sector readiness artifacts per wave |
| Strategy open decisions not yet time-bounded | Some adapter/interface/deployment decisions remain open and can cause roadmap drift if not explicitly resolved | Planned: convert open decisions into dated decision records and tie each to a concrete execution slice |
| Canonical UI roadmap contract | Needed to avoid future UI-vs-API drift | Deferred by design under API-first posture; strategy documented in `INTERFACE_STRATEGY.md` |
| Private/self-hosted deployment certification model | Needed before strict enterprise self-hosted support claims | Planned; documented as deferred in `DEPLOYMENT_MODELS.md` pending maturity gates |

---

## 4) Drift Detection Workflow

Use this workflow on architecture-impacting changes:

1. Update strategic decision docs in `docs/strategy/`.
2. Update this matrix with code/API/test anchors.
3. Update epic status/evidence in `execution-board-12-gaps.md` for affected gaps.
4. Run tests and architecture gates.
5. Verify RC signoff artifacts remain healthy.
6. Capture any accepted divergence with rationale and owner.

---

## 5) Update Checklist

- Are all new strategic decisions represented in this matrix?
- Does each decision map to at least one code anchor and one test anchor?
- Are API control points documented where customer configuration is expected?
- Are gate/evidence anchors still valid and executable?

If any answer is "no", documentation is incomplete.
