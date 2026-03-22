<!--
File: next-directions.md
Path: next-directions.md
Role: Architecture-aligned next implementation directions and prioritization.
Used By:
 - AGENTS.md
 - goal.md
 - README.md
Depends On:
 - goal.md
 - core.md
 - adapter-strategy.md
 - traceability-matrix.md
 - monetization-strategy.md
 - interface-strategy.md
 - execution-board-12-gaps.md
Notes:
 - Keep aligned with GOAL.md §14 Practical next alignment steps and README §Next implementation slice entrypoints.
 - Update when architecture-impacting decisions or gaps change.
-->

# Next Directions (Architecture-Aligned)

## Governance Metadata

- Status: `active`
- Owner: `Savin I. Razvan`
- Version: `1.9.0`
- Last Reviewed: `2026-03-15`
- Review Cadence: `monthly`
- Decision Scope: `Prioritized implementation directions derived from docs/strategy strategy docs.`

## Source of Truth

This document consolidates next-step guidance from:
- `goal.md` §14 Practical next alignment steps
- `README.md` §Next implementation slice entrypoints
- `traceability-matrix.md` §3 Current known gaps
- `execution-board-12-gaps.md` (epic-level sequencing, test, and rollback guidance)

---

## 1) Tier 1 — Adapter Portability and Ecosystem

| Direction | Why | References |
|-----------|-----|------------|
| **Finalize external package boundaries** | Adapters must be standalone; no monorepo-only imports. Core contracts + adapter SDK must be externalizable. | GOAL §11, TRACEABILITY §3 (full external adapter portability gap) |
| **Complete `exo-adapter-openai` extraction** | Enables independent adapter distribution and partner ecosystem. First adapter sets the pattern. External install certification complete: all three packages install cleanly in an isolated venv with zero monorepo-relative imports; `scripts/packages/external_install_smoke.py` gates the external install path in CI. Next: publish certification automation (PyPI upload + version tagging). | TRACEABILITY §3, ADAPTER_STRATEGY §4 |
| **Define adapter certification matrix** | Baseline and expansion providers require explicit conformance criteria, compatibility matrices, and release gates. | GOAL §14.2, ADAPTER_STRATEGY §3, §19 |
| **Add northbound OpenAI-compatible gateway surface** | External apps need drop-in `/v1` compatibility while keeping internal orchestration contracts provider-neutral. | INTERFACE_STRATEGY §2, TRACEABILITY §3 (customer API surface parity gap) |
| **Split OpenAI execution modes by contract (`chat` vs `agents`)** | Improves reliability and testability by separating provider execution concerns from orchestration concerns. | GOAL §6, GOAL §11, ADAPTER_STRATEGY §2 |
| **Add explicit provider endpoint protocol typing (`api_type`)** | Adapter expansion requires protocol-aware registration (`openai_native`, `openai_compatible`, `custom`) instead of hardcoded defaults. | ADAPTER_STRATEGY §19.2, TRACEABILITY §3 |
| **Ship universal OpenAI-compatible adapter baseline** | Fastest safe path for onboarding additional providers while preserving provider-neutral core boundaries. | ADAPTER_STRATEGY §19.4, §19.6 |
| **Onboard expansion wave (Mistral, DeepSeek, Qwen, Moonshot, Zhipu, MiniMax)** | Increases provider optionality and regional coverage with minimal core churn. | ADAPTER_STRATEGY §19.5 |
| **Build hybrid/native wave (Hugging Face, Aleph Alpha)** | Needed for provider-specific capabilities and reliability beyond universal compatibility abstractions. | ADAPTER_STRATEGY §19.5, §19.6 |
| **Integrate DeepL through governed tool/service lane** | Translation/service integrations must remain deterministic-first, policy-wrapped, and auditable. | ADAPTER_STRATEGY §19.4, CORE runtime safety invariants |
| **Automate adapter publish certification evidence** | External install certification exists; release-scale publication and version evidence automation is still needed. | TRACEABILITY §3 (portability gap), ADAPTER_STRATEGY §12, §19.8 |
| **Add runtime provider router (health/cost/policy-aware)** | Gateway-grade routing requires health-aware primary selection, governed fallback, and telemetry-visible decisions without safety downgrade. | TRACEABILITY §3, GOAL §7 |

---

## 2) Tier 2 — Monetization and Entitlement

| Direction | Why | References |
|-----------|-----|------------|
| **Entitlement enforcement layer** | Tier claims must map to explicit enforceable controls. Needed for clean monetization boundary. | README §next slice, TRACEABILITY §3 (entitlement operability), ENTITLEMENT_MATRIX |
| **Monetization feature flags and entitlement hooks** | Governance surfaces (policy, audit, runtime) need tier-aware gating for Pro/Enterprise. | GOAL §14.4 |
| **Tier-aware audit evidence** | Entitlement decisions must be auditable and exportable. | README §next slice |
| **Governance ingress plane (pre-model gate chain)** | Safety decisions must happen before model/runtime execution, with non-bypassable allow/deny/escalate outcomes and clear reason codes. | GOAL §3, INTERFACE_STRATEGY §6, MONETIZATION_STRATEGY §2 |
| **Predefined + custom gate/policy model with latency budgets** | Customers need controlled flexibility (templates + custom rules/plugins) without degrading reliability or p95 turn latency; profile-specific ingress SLO thresholds + per-profile release reporting baseline are now implemented; external classifier model-routing with transparent fallback + evidence anchors now implemented. | MONETIZATION_STRATEGY §3, ENTITLEMENT_MATRIX §4, TRACEABILITY §3 |
| **Add first-class human approval workflow surface** | `review_required` and escalation outcomes need explicit approve/reject lifecycle APIs with audit-linked transitions. | TRACEABILITY §3, INTERFACE_STRATEGY §9 |
| **Complete advanced entitlement depth backlog** | External classifier model-routing depth and external signed-plugin package ingestion are still planned and must be tier-hard-gated. | ENTITLEMENT_MATRIX §3, §5 |
| **Wire external classifier adapter injection end-to-end** | Classifier routing contract exists, but production value depends on explicit wiring from tenant/runtime configuration into ingress gate chains. | TRACEABILITY §3, ENTITLEMENT_MATRIX §5 |
| **Add external signed-plugin package ingestion workflow** | Current signed plugin model is baseline and registry-bound; enterprise depth requires publisher onboarding, signature trust lifecycle, and rollback controls. | ENTITLEMENT_MATRIX §5, TRACEABILITY §3 |
| **Add token-aware budget/rate governance at inference edge** | Tenant-safe spend and abuse controls need token/cost-aware deny/escalate/reroute policies beyond request-count limits. | MONETIZATION_STRATEGY §3, TRACEABILITY §3 |
| **Deepen MCP governance policy surface** | Trust-tier and health checks should be complemented with per-server tool allow/deny controls and credential-scope policy enforcement. | TRACEABILITY §3, GOAL §7 |

---

## 3) Tier 3 — Customer Enablement and Operations

| Direction | Why | References |
|-----------|-----|------------|
| **Customer-facing API integration guide (chat/agents/workflow + governance ingress)** | Customers need explicit integration paths for OpenAI-compatible chat APIs, Agents SDK-style execution, orchestration workflows, and turn-level safety governance controls — baseline tier-aware guide delivered at `docs/api/customer-api-integration-guide.md`. | GOAL §14.3, INTERFACE_STRATEGY §2 |
| **Deployment certification and support-boundary automation** | Private/self-hosted support claims require explicit support and responsibility boundaries. | README §next slice, TRACEABILITY §3 (deployment model gap), DEPLOYMENT_MODELS |
| **Add first-class OTel/Prometheus observability export path** | Enterprise operations commonly require standard telemetry sinks alongside current local/in-memory observability primitives. | TRACEABILITY §3, COMPLIANCE_PROFILE_MATRIX §3 |
| **Codify compliance operations packaging per wave** | SOC2/GDPR, then HIPAA/PCI/public-sector readiness claims need runbooks, control narratives, and evidence packaging artifacts. | COMPLIANCE_PROFILE_MATRIX §3 |

---

## 4) Tier 4 — Documentation and Alignment

| Direction | Why | References |
|-----------|-----|------------|
| **Keep GOAL, AGENTS, README, ADAPTER_STRATEGY synchronized** | Prevents direction drift. Edit docs/strategy first when strategy changes. | GOAL §14.5 |
| **Update traceability-matrix on architecture-impacting changes** | Ensures strategy decisions map to code/API/test anchors. | TRACEABILITY §4 Drift Detection Workflow |
| **Resolve open strategy decisions with explicit decision records** | Adapter SLA/cert scope, interface stability, and deployment support boundaries should not remain open-ended across strategy docs. | ADAPTER_STRATEGY §17, INTERFACE_STRATEGY §13, DEPLOYMENT_MODELS §8 |

---

## 5) Out of Scope (Deferred by Design)

- **UI/dashboard** — API-first posture; optional API-driven console may be added later. Customer builds own UI on eXo-brain APIs. See `INTERFACE_STRATEGY.md` §2.
- **Purge of historical UI references in docs** — Low priority; historical/planning docs may retain UI mentions for future reference.
- **Unbounded customer code execution for safety plugins** — Deferred until signed plugin packaging, sandbox boundaries, and strict policy/latency controls are production-ready.

---

## 6) Core Open Risks (Monitor, Don't Block)

From `core.md` §11:
- Contract drift across adapters
- Policy latency inflation on hot paths
- Fallback complexity under mixed providers
- Operational blind spots (correlation IDs, run/audit evidence)
- Excessively permissive customer customization that could weaken baseline trust guarantees

---

## 7) Alignment Checklist Before Starting a Slice

From `goal.md` §13:
- Does this preserve provider-neutral core boundaries?
- Can a customer configure it via API without code patching core?
- Does policy middleware still wrap all side-effect paths?
- Is deterministic execution still enforced for risky/state-changing calls?
- Are audit and observability events complete and verifiable?
- Is the change compatible with adapter contract version policy?

If any answer is "no", stop and redesign before merging.
