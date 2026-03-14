<!--
File: NEXT_DIRECTIONS.md
Path: architecture-goals/NEXT_DIRECTIONS.md
Role: Architecture-aligned next implementation directions and prioritization.
Used By:
 - AGENTS.md
 - architecture-goals/GOAL.md
 - architecture-goals/README.md
Depends On:
 - architecture-goals/GOAL.md
 - architecture-goals/CORE.md
 - architecture-goals/ADAPTER_STRATEGY.md
 - architecture-goals/TRACEABILITY_MATRIX.md
 - architecture-goals/MONETIZATION_STRATEGY.md
 - architecture-goals/INTERFACE_STRATEGY.md
Notes:
 - Keep aligned with GOAL.md §14 Practical next alignment steps and README §Next implementation slice entrypoints.
 - Update when architecture-impacting decisions or gaps change.
-->

# Next Directions (Architecture-Aligned)

## Governance Metadata

- Status: `active`
- Owner: `Savin I. Razvan`
- Version: `1.2.0`
- Last Reviewed: `2026-03-14`
- Review Cadence: `monthly`
- Decision Scope: `Prioritized implementation directions derived from architecture-goals strategy docs.`

## Source of Truth

This document consolidates next-step guidance from:
- `architecture-goals/GOAL.md` §14 Practical next alignment steps
- `architecture-goals/README.md` §Next implementation slice entrypoints
- `architecture-goals/TRACEABILITY_MATRIX.md` §3 Current known gaps

---

## 1) Tier 1 — Adapter Portability and Ecosystem

| Direction | Why | References |
|-----------|-----|------------|
| **Finalize external package boundaries** | Adapters must be standalone; no monorepo-only imports. Core contracts + adapter SDK must be externalizable. | GOAL §11, TRACEABILITY §3 (full external adapter portability gap) |
| **Complete `exo-adapter-openai` extraction** | Enables independent adapter distribution and partner ecosystem. First adapter sets the pattern. | TRACEABILITY §3, ADAPTER_STRATEGY §4 |
| **Define adapter certification matrix** | Five target providers (OpenAI, Gemini, Anthropic, xAI, Meta) need explicit conformance criteria. | GOAL §14.2, ADAPTER_STRATEGY §3 |
| **Add northbound OpenAI-compatible gateway surface** | External apps need drop-in `/v1` compatibility while keeping internal orchestration contracts provider-neutral. | INTERFACE_STRATEGY §2, TRACEABILITY §3 (customer API surface parity gap) |
| **Split OpenAI execution modes by contract (`chat` vs `agents`)** | Improves reliability and testability by separating provider execution concerns from orchestration concerns. | GOAL §6, GOAL §11, ADAPTER_STRATEGY §2 |

---

## 2) Tier 2 — Monetization and Entitlement

| Direction | Why | References |
|-----------|-----|------------|
| **Entitlement enforcement layer** | Tier claims must map to explicit enforceable controls. Needed for clean monetization boundary. | README §next slice, TRACEABILITY §3 (entitlement operability), ENTITLEMENT_MATRIX |
| **Monetization feature flags and entitlement hooks** | Governance surfaces (policy, audit, runtime) need tier-aware gating for Pro/Enterprise. | GOAL §14.4 |
| **Tier-aware audit evidence** | Entitlement decisions must be auditable and exportable. | README §next slice |
| **Governance ingress plane (pre-model gate chain)** | Safety decisions must happen before model/runtime execution, with non-bypassable allow/deny/escalate outcomes and clear reason codes. | GOAL §3, INTERFACE_STRATEGY §6, MONETIZATION_STRATEGY §2 |
| **Predefined + custom gate/policy model with latency budgets** | Customers need controlled flexibility (templates + custom rules/plugins) without degrading reliability or p95 turn latency. | MONETIZATION_STRATEGY §3, ENTITLEMENT_MATRIX §4, TRACEABILITY §3 |

---

## 3) Tier 3 — Customer Enablement and Operations

| Direction | Why | References |
|-----------|-----|------------|
| **Customer-facing API integration guide (chat/agents/workflow + governance ingress)** | Customers need explicit integration paths for OpenAI-compatible chat APIs, Agents SDK-style execution, orchestration workflows, and turn-level safety governance controls. | GOAL §14.3, INTERFACE_STRATEGY §2 |
| **Deployment certification and support-boundary automation** | Private/self-hosted support claims require explicit support and responsibility boundaries. | README §next slice, TRACEABILITY §3 (deployment model gap), DEPLOYMENT_MODELS |

---

## 4) Tier 4 — Documentation and Alignment

| Direction | Why | References |
|-----------|-----|------------|
| **Keep GOAL, AGENTS, README, ADAPTER_STRATEGY synchronized** | Prevents direction drift. Edit architecture-goals first when strategy changes. | GOAL §14.5 |
| **Update TRACEABILITY_MATRIX on architecture-impacting changes** | Ensures strategy decisions map to code/API/test anchors. | TRACEABILITY §4 Drift Detection Workflow |

---

## 5) Out of Scope (Deferred by Design)

- **UI/dashboard** — API-first posture; optional API-driven console may be added later. Customer builds own UI on eXo-brain APIs. See `INTERFACE_STRATEGY.md` §2.
- **Purge of historical UI references in docs** — Low priority; historical/planning docs may retain UI mentions for future reference.
- **Unbounded customer code execution for safety plugins** — Deferred until signed plugin packaging, sandbox boundaries, and strict policy/latency controls are production-ready.

---

## 6) Core Open Risks (Monitor, Don't Block)

From `architecture-goals/CORE.md` §11:
- Contract drift across adapters
- Policy latency inflation on hot paths
- Fallback complexity under mixed providers
- Operational blind spots (correlation IDs, run/audit evidence)
- Excessively permissive customer customization that could weaken baseline trust guarantees

---

## 7) Alignment Checklist Before Starting a Slice

From `architecture-goals/GOAL.md` §13:
- Does this preserve provider-neutral core boundaries?
- Can a customer configure it via API without code patching core?
- Does policy middleware still wrap all side-effect paths?
- Is deterministic execution still enforced for risky/state-changing calls?
- Are audit and observability events complete and verifiable?
- Is the change compatible with adapter contract version policy?

If any answer is "no", stop and redesign before merging.
