<!--
File: EXECUTION_BOARD_12_GAPS.md
Path: execution-board-12-gaps.md
Role: Execution-ready board for the 12 prioritized architecture gaps, including safety gates, customization controls, test evidence, and rollback paths.
Used By:
 - README.md
 - next-directions.md
 - traceability-matrix.md
 - adapter-strategy.md
Depends On:
 - goal.md
 - core.md
 - adapter-strategy.md
 - entitlement-matrix.md
 - interface-strategy.md
 - traceability-matrix.md
Notes:
 - Keep this board implementation-focused; strategy remains in companion docs.
 - Update epic statuses and evidence anchors when slices are merged.
-->

# Execution Board: 12 Priority Gaps

## Governance Metadata

- Status: `active`
- Owner: `Savin I. Razvan`
- Version: `1.0.1`
- Last Reviewed: `2026-03-24`
- Review Cadence: `monthly`
- Decision Scope: `Implementation sequencing and acceptance model for the 12 agreed architecture gap themes.`

## 1) Purpose

This board translates the agreed gap list into implementation-ready epics with:
- clear rollout order,
- safety and governance invariants,
- customer customization controls,
- explicit acceptance and rollback criteria.

Use this document as the execution companion to:
- `next-directions.md` (priority direction),
- `traceability-matrix.md` (strategy-to-code mapping),
- `adapter-strategy.md` (adapter-specific rollout rules),
- [`docs/plans/control-plane-product-alignment-plan.md`](../plans/control-plane-product-alignment-plan.md) (control plane vocabulary, customer bridge phases, enterprise evidence checklist).

## 2) Non-Negotiable Guardrails

Every epic in this board must preserve all of the following:
- provider-neutral core boundaries (no provider SDK logic in `src/core/*`),
- deterministic-first handling for risky/state-changing side effects,
- policy pre/post checks for every side-effect path,
- complete audit continuity (`correlation_id` and policy reason codes),
- API-first customer control with safe defaults and explicit opt-in for risky depth.

Customization principle:
- customers can tighten, specialize, and sequence controls,
- customers cannot disable baseline trust controls that protect safety/compliance.

## 3) Need Scoring Model

Scoring scale:
- `0` = no practical need
- `1` = optional niche
- `2` = useful for specific teams
- `3` = broadly useful, not blocking
- `4` = important for adoption/operations
- `5` = critical for production competitiveness

Weighted Need formula:
- `0.20 * Normal Users + 0.35 * Customer Teams + 0.45 * Enterprise`

## 4) Prioritized 12-Gap Scoreboard

| Epic | Gap Theme | Normal Users | Customer Teams | Enterprise | Weighted Need | Priority |
|---|---|---:|---:|---:|---:|---|
| E01 | Northbound `/v1` compatibility plane | 5 | 5 | 4 | 4.55 | P0 |
| E02 | Human approval workflow lifecycle | 2 | 4 | 5 | 4.05 | P0 |
| E03 | Runtime provider router (health/cost/policy) | 4 | 5 | 5 | 4.80 | P0 |
| E04 | OTel + Prometheus observability exporters | 2 | 4 | 5 | 4.05 | P1 |
| E05 | Provider protocol explicitness (`api_type`) | 2 | 4 | 4 | 3.60 | P1 |
| E06 | Adapter portfolio expansion execution | 4 | 5 | 4 | 4.35 | P1 |
| E07 | Adapter publish/certification automation | 2 | 4 | 5 | 4.05 | P1 |
| E08 | External classifier end-to-end wiring depth | 1 | 3 | 5 | 3.50 | P2 |
| E09 | Signed plugin external ingestion lifecycle | 1 | 3 | 5 | 3.50 | P2 |
| E10 | Token/cost governance at inference edge | 4 | 5 | 5 | 4.80 | P0 |
| E11 | MCP governance depth (tool + credential policy) | 2 | 4 | 5 | 4.05 | P1 |
| E12 | Deployment certification + compliance ops packaging | 1 | 3 | 5 | 3.50 | P2 |

## 5) Recommended Delivery Waves

## Wave A (Weeks 0-6): Adoption + Safety Foundation
- E05 protocol explicitness
- E01 `/v1` compatibility
- E02 approval lifecycle
- E03 runtime provider router
- E10 token/cost governance

## Wave B (Weeks 6-12): Enterprise Interoperability + Portability
- E04 OTel/Prom exporters
- E06 adapter expansion lanes
- E07 publish/cert automation
- E11 MCP governance depth

## Wave C (Weeks 12-18): Advanced Governance Depth + Operational Packaging
- E08 external classifier depth
- E09 signed plugin external ingestion
- E12 deployment/compliance certification packaging

## 6) Epic Implementation Cards

### E01 - Northbound `/v1` Compatibility Plane (P0)

- Objective: provide drop-in OpenAI SDK compatibility without violating core boundaries.
- Implementation slices:
  - S1: add `/v1/chat/completions`, `/v1/models` ingress routes mapped to existing turn orchestration.
  - S2: add SSE event translation parity and standardized error envelopes.
  - S3: add compatibility conformance tests against OpenAI client behaviors.
- Safety requirements:
  - preserve policy deny/escalate reason codes through compatibility adapter.
  - preserve deterministic execution requirements for risky tool paths.
- Customization controls:
  - per-tenant enable/disable for `/v1` surface.
  - per-tenant provider allowlist and fallback chain remains API-configurable.
- Integration anchors:
  - `src/api/app.py`
  - `src/api/routers/turns.py`
  - `src/runtime/openai_compatible_runtime.py`
  - `src/api/schemas/*` (compat request/response schemas)
- Acceptance evidence:
  - OpenAI SDK base-URL/key swap works for core paths.
  - policy and audit continuity validated in integration tests.
- Rollback:
  - keep `/turns` as canonical path and gate `/v1` behind feature flag until parity passes.

### E02 - Human Approval Workflow Lifecycle (P0)

- Objective: convert `review_required` from signal into executable approve/deny workflow.
- Implementation slices:
  - S1: introduce approval entity model (`pending`, `approved`, `denied`, `expired`).
  - S2: add approval action APIs with authz controls.
  - S3: wire turn/tool pause-resume behavior and timeout policy.
- Safety requirements:
  - no escalated operation resumes without explicit decision or policy-defined timeout path.
  - approval decisions are immutable audit events linked to `correlation_id`.
- Customization controls:
  - tenant-configurable timeout strategy (`auto_deny`, `auto_escalate`, `manual_only`).
  - configurable approval channels/roles by tier.
- Integration anchors:
  - `src/policies/risk_gates.py`
  - `src/policies/ingress_gates.py`
  - `src/api/routers/turns.py`
  - `src/api/routers/*` (new approval routes)
- Acceptance evidence:
  - lifecycle tests cover pending -> approved/denied/expired.
  - audit export/verify includes approval chain evidence.
- Rollback:
  - disable approval actions and revert to current escalate behavior with deny-safe default.

### E03 - Runtime Provider Router (P0)

- Objective: move from static fallback to health/cost/policy-aware routing.
- Implementation slices:
  - S1: add provider router module with health-aware primary selection.
  - S2: add weighted routing inputs (cost/latency/capability/policy constraints).
  - S3: add routing telemetry and deterministic non-regression checks.
- Safety requirements:
  - route changes cannot downgrade deterministic or policy requirements.
  - every route decision emits auditable reason and selected provider chain.
- Customization controls:
  - tenant-level routing policy profiles (`availability_first`, `cost_balanced`, `latency_first`).
  - hard provider deny/allow constraints by tenant or key.
- Integration anchors:
  - `src/config/provider_registry.py`
  - `src/runtime/adapter_factory.py`
  - `src/runtime/*` (new routing module)
- Acceptance evidence:
  - failover tests prove safe continuity across provider failures.
  - route decision telemetry visible in runtime and audit outputs.
- Rollback:
  - revert to ordered static fallback mode with router feature flag off.

### E04 - OTel + Prometheus Export Path (P1)

- Objective: add enterprise-standard telemetry sinks without losing local diagnostics.
- Implementation slices:
  - S1: keep existing logging/tracing contracts; add pluggable exporter interfaces.
  - S2: implement OpenTelemetry trace exporter and context propagation.
  - S3: implement Prometheus metric exposition for core runtime signals.
- Safety requirements:
  - exporter failures must not block turn execution.
  - sensitive fields remain redacted before export.
- Customization controls:
  - selectable telemetry sinks per deployment profile.
  - tenant/operation-level metric label filtering policy.
- Integration anchors:
  - `src/observability/logging.py`
  - `src/observability/tracing.py`
  - `src/observability/metrics.py`
  - `src/api/routers/runtime_control.py`
- Acceptance evidence:
  - correlation IDs can be traced across logs/spans/metrics.
  - exporter health checks and sample dashboards validated in CI artifacts.
- Rollback:
  - keep current JSONL/in-memory exporters as default fallback.

### E05 - Provider Protocol Explicitness (`api_type`) (P1)

- Objective: enforce explicit provider protocol typing during provider registration.
- Implementation slices:
  - S1: add schema field and validation (`openai_native`, `openai_compatible`, `custom`).
  - S2: persist and expose protocol type through provider APIs.
  - S3: add backward-compatible default handling for old payloads.
- Safety requirements:
  - unknown protocol type fails closed with explicit reason code.
  - protocol mismatch blocks unsafe runtime assumptions.
- Customization controls:
  - customer can register mixed protocol providers with explicit behavior.
  - per-provider capability overrides remain policy-guarded.
- Integration anchors:
  - `src/api/schemas/provider_schemas.py`
  - `src/api/routers/providers.py`
  - `src/config/provider_registry.py`
- Acceptance evidence:
  - provider registration tests cover valid/invalid/missing protocol cases.
- Rollback:
  - preserve compatibility fallback only for pre-existing provider records.

### E06 - Adapter Portfolio Expansion Execution (P1)

- Objective: execute expansion lanes safely for added provider portfolio.
- Implementation slices:
  - S1: universal lane onboarding for Mistral/DeepSeek/Qwen.
  - S2: hybrid/native path for Hugging Face and Aleph Alpha.
  - S3: service/tool lane integration for DeepL with deterministic wrappers.
  - S4: feature-flagged onboarding for Moonshot/Zhipu/MiniMax.
  - S5: discovery spikes for Minerva/Velvet with go/no-go records.
- Safety requirements:
  - every new provider path passes contract conformance and safety replay tests.
  - fallback behavior preserves policy and deterministic guarantees.
- Customization controls:
  - per-tenant provider allowlist and ordered fallback.
  - per-provider kill switch and staged rollout percentage.
- Integration anchors:
  - `exo-brain-adapter-sdk` (PyPI; authored in eXo_adapters)
  - `exo-adapter-openai` (PyPI)
  - planned adapter packages (`exo-adapter-*`)
  - `src/runtime/adapter_factory.py`
- Acceptance evidence:
  - cross-adapter workflow parity tests for at least 3 providers.
  - staged rollout evidence with safe fallback behavior.
- Rollback:
  - disable affected provider via feature flag and route to certified fallback chain.

### E07 - Adapter Publish and Certification Automation (P1)

- Objective: automate build, conformance, smoke, and publish evidence for adapters.
- Implementation slices:
  - S1: define adapter certification manifest and evidence schema.
  - S2: automate version/tag/build/smoke/conformance gates in CI.
  - S3: publish matrix artifact tied to adapter/core-contract compatibility.
- Safety requirements:
  - publishing blocked on any P0 contract/safety failure.
  - signed release evidence required for certified adapters.
- Customization controls:
  - teams can choose strict vs progressive certification mode by environment.
- Integration anchors:
  - `scripts/packages/external_install_smoke.py`
  - `tests/packages/*`
  - CI workflow configs and release scripts
- Acceptance evidence:
  - reproducible adapter certification artifacts per release.
- Rollback:
  - block publish and keep previously certified adapter versions pinned.

### E08 - External Classifier Wiring Depth (P2)

- Objective: wire external classifier adapters end-to-end from configuration to ingress decisions.
- Implementation slices:
  - S1: inject classifier adapter from tenant/runtime policy overlays.
  - S2: enforce timeout and transparent fallback to heuristic path.
  - S3: emit classifier telemetry for decision source and confidence.
- Safety requirements:
  - classifier timeout cannot block ingress indefinitely.
  - fallback behavior must be explicit and auditable.
- Customization controls:
  - per-tenant mode (`off`, `shadow`, `enforce`) and threshold tuning.
  - allowlist of trusted classifier adapters by tier.
- Integration anchors:
  - `src/policies/ingress_gates.py`
  - `src/policies/ingress_classifier_router.py`
  - `src/tenancy/policy_overlay.py`
  - `src/api/routers/tenants.py`
- Acceptance evidence:
  - tests for injection path, timeout path, and fallback telemetry.
- Rollback:
  - default to heuristic classifier mode with external injection disabled.

### E09 - Signed Plugin External Ingestion Lifecycle (P2)

- Objective: move from registry-static trusted refs to controlled external package ingestion.
- Implementation slices:
  - S1: add signer onboarding and trust store lifecycle controls.
  - S2: add package ingestion validation (signature, compatibility, sandbox constraints).
  - S3: add rollback and revoke paths for compromised packages.
- Safety requirements:
  - unsigned or incompatible plugins fail closed.
  - active-run safety guard prevents unsafe unload/reload.
- Customization controls:
  - tenant/plugin allowlist and signer trust scopes.
  - policy on plugin permissions by environment/profile.
- Integration anchors:
  - `src/policies/ingress_signed_plugins.py`
  - `src/api/routers/tenants.py`
  - planned plugin ingestion modules
- Acceptance evidence:
  - signature verification and trust revocation tests.
  - audit trail includes signer/package decision metadata.
- Rollback:
  - revert to registry-static trusted plugin references.

### E10 - Token/Cost Governance at Inference Edge (P0)

- Objective: add token-aware budget controls and policy actions at runtime edge.
- Implementation slices:
  - S1: define budget entities by key/team/tenant.
  - S2: add policy actions (`allow`, `deny`, `escalate`, `reroute`) on threshold states.
  - S3: expose budget telemetry and admin controls.
- Safety requirements:
  - budget enforcement must be deterministic and auditable.
  - actions on budget breach must fail-safe by policy.
- Customization controls:
  - per-tenant quota model and threshold actions.
  - burst and grace-window settings with explicit caps.
- Integration anchors:
  - `src/tenancy/quotas.py`
  - `src/tenancy/rate_limiter.py`
  - `src/api/routers/runtime_control.py`
  - planned token budget governance modules
- Acceptance evidence:
  - tests for threshold crossing, policy action selection, and audit emission.
- Rollback:
  - revert to request-count limits and disable token-aware enforcement flags.

### E11 - MCP Governance Depth (P1)

- Objective: add explicit MCP tool filtering and credential scope policy.
- Implementation slices:
  - S1: define per-server tool allow/deny policy surface.
  - S2: enforce scoped credential policy at execution boundary.
  - S3: emit MCP policy decision telemetry and audits.
- Safety requirements:
  - default stance is deny unless explicitly allowed by policy.
  - credential scope violations are blocked and audited.
- Customization controls:
  - tenant/admin policy overlays per MCP server and tool group.
  - environment-based credential scope templates.
- Integration anchors:
  - `src/mcp/mcp_registry.py`
  - `src/mcp/mcp_tool_adapter.py`
  - planned MCP policy modules and APIs
- Acceptance evidence:
  - tests for allow/deny filtering and scoped credential failures.
- Rollback:
  - retain trust-tier + health gating with stricter global deny profile.

### E12 - Deployment Certification + Compliance Ops Packaging (P2)

- Objective: make private/self-hosted support and compliance claims operationally auditable.
- Implementation slices:
  - S1: codify deployment certification checks per model/tier.
  - S2: build compliance operations artifact catalog and runbooks (SOC2/GDPR first, then HIPAA/PCI/public-sector).
  - S3: tie evidence generation into release verification gates.
- Safety requirements:
  - no enterprise support claim without matching evidence package.
  - deployment profile mismatch blocks certification status.
- Customization controls:
  - profile-driven control bundles selectable by customer deployment.
  - explicit accepted-divergence records for customer-specific variants.
- Integration anchors:
  - `deployment-models.md`
  - `compliance-profile-matrix.md`
  - `scripts/release/verify_gates.py`
  - `docs/operations/*` (runbooks and evidence references)
- Acceptance evidence:
  - executable certification checklists and dry-run audit traceability.
- Rollback:
  - downgrade support posture to non-certified profile until gaps close.

## 7) Cross-Epic Definition of Done

For each epic to close:
- all acceptance tests pass (happy path, failure path, timeout/retry where relevant),
- traceability anchors are updated in `traceability-matrix.md`,
- feature flags and rollback paths are validated in staging,
- release evidence artifacts include the new control outcomes,
- docs and API contract references are updated before merge.

## 8) Operating Cadence

Recommended review loop:
- weekly: epic status + blocker review,
- per merged slice: evidence and rollback validation,
- monthly: rescore priorities based on adoption and enterprise feedback.

If new market-critical gaps appear:
- append to backlog with scores,
- do not displace P0 epics unless risk justification is documented.
