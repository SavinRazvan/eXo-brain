<!--
File: control-plane-product-alignment-plan.md
Path: docs/plans/control-plane-product-alignment-plan.md
Role: Executable plan to keep product narrative (control plane, monetization for safety, integration surfaces) aligned across strategy, architecture, and customer-facing docs.
Used By:
 - Maintainers, GTM, enterprise-auditor alignment passes
Depends On:
 - docs/strategy/governed-execution-positioning.md
 - docs/strategy/goal.md
 - docs/strategy/traceability-matrix.md
 - docs/architecture/ARCHITECTURE.md
Notes:
 - This plan does not replace adapter-ecosystem or tenant-tool plans; it cross-cuts them with vocabulary and evidence discipline.
-->

# Control plane product alignment — execution plan

## 1. Executive snapshot

**Product thesis (locked):** eXo-brain is the **control plane** for governed AI execution. Customers keep provider/model connectivity; **monetization targets safety and governance** (policy, deterministic tools, audit, entitlements, runtime control), not commodity LLM resale.

**Integration thesis:** Three **named surfaces** avoid “adapter” ambiguity:

| Surface | What it is | Primary docs / code |
|--------|------------|---------------------|
| **A — Provider runtime adapter** | How the **hosted runtime** reaches a provider/model **outbound**, behind the adapter wall. **Source** lives in **separate adapter repos**; this control-plane repo owns `src/runtime/*` and contracts consumption only (`packages/*` **transitional** until extraction). | `docs/strategy/adapter-strategy.md`, `src/runtime/*` |
| **B — Control plane API** | Authoritative **ingress** for tenants: sessions, turns, policy, tools, agents, audit, providers (REST / SSE / WS). | `docs/strategy/interface-strategy.md`, `src/api/routers/*`, `docs/api/customer-api-integration-guide.md` |
| **C — Customer bridge** | How **customer apps** attach their loop: native API integration today; optional OpenAI-shaped **`POST /v1/chat/completions`** (`EXO_ENABLE_OPENAI_COMPAT_GATEWAY`); **planned** thin client SDK with **same governance spine** as HTTP (no bypass path). | `docs/archive/plans/northbound-v1-gateway.md`, `src/api/routers/openai_gateway.py` |

**BYOC / data-plane connectors** (workers, customer infra) are an **additional** pattern; they must **not** weaken policy or deterministic execution invariants.

**Canonical vocabulary** lives in `docs/strategy/governed-execution-positioning.md` (including **Repository boundary**) and `docs/strategy/goal.md` (section 5a).

---

## 2. Baseline documentation slice (closed — archived)

The **baseline alignment checklist** (all items) is **100% complete** and recorded as a frozen closure artifact:

- **[`docs/archive/plans/control-plane-product-alignment-baseline-slice-closed.md`](../archive/plans/control-plane-product-alignment-baseline-slice-closed.md)**

Ongoing product alignment work continues in **section 3** (Phases **L1–L4**) and **sections 4–6** below.

---

## 3. Later phases (improve continuously)

### Phase L1 — Customer bridge hardening (product + engineering)

- Define **minimal SDK** scope: auth, session/run identity, streaming, tool result submission; explicitly **forbid** hidden provider SDK paths that skip policy.
- **Conformance suite**: golden scenarios or contract tests that prove SDK and HTTP share the same deny/audit outcomes.
- Update `customer-api-integration-guide.md` and `interface-strategy.md` when SDK ships.

**Exit criteria:** Versioned SDK package; CI tests for parity; traceability row with code anchors.

### Phase L2 — Enterprise evidence pack

- Data-flow and shared-responsibility narratives aligned with `deployment-models.md` and `compliance-profile-matrix.md`.
- Threat-model updates for tenant isolation, tokens, MCP/supply chain (tie to `execution-board-12-gaps.md` themes).
- Honest mapping: which tier claims are **enforceable** in code vs **planned** (`entitlement-matrix.md`).

**Exit criteria:** Assessor-ready outline (not legal advice); gaps explicitly labeled Planned.

### Phase L3 — Strategy review cadence

- Monthly: `docs/strategy/README.md` closure snapshot + `traceability-matrix.md` §3 gap review.
- On each architecture-impacting PR: `check_governance_consistency.py` when paths warrant; alignment artifacts per `.cursor/rules/advisory-audit-alignment-enforcement.mdc`.

### Phase L4 — Architecture doc pass (separate slice)

- `docs/architecture/ARCHITECTURE.md` §3 (northbound) + diagram note for surfaces A/B/C.
- Keep **single source of truth** for gate order in code (`turns.py` / plans); architecture links only.

---

## 4. File ownership (who to update when the model changes)

| Topic | Owner doc |
|-------|-----------|
| Vocabulary + positioning | `governed-execution-positioning.md`, `goal.md` |
| Provider packages / semver / certification | `adapter-strategy.md`, `adapter-compatibility-matrix.md` |
| API + bridge + future SDK | `interface-strategy.md`, `docs/archive/plans/northbound-v1-gateway.md` (archived URL map), customer guide |
| Monetization + tiers | `monetization-strategy.md`, `entitlement-matrix.md` |
| Code↔strategy mapping | `traceability-matrix.md` |
| Priorities | `next-directions.md`, `execution-board-12-gaps.md` |
| Deployment / compliance claims | `deployment-models.md`, `compliance-profile-matrix.md` |

---

## 5. Discussion agenda (after this merge)

Use this checklist for the strategy / architecture / plans review meeting:

1. **Surfaces A/B/C:** Any rename pushback from field teams? Lock glossary for one quarter.
2. **Monetization:** Which Pro/Enterprise claims are enforceable **today** vs documentation-only?
3. **Bridge SDK:** Target customer (Python only first vs language-agnostic HTTP)?
4. **BYOC:** How connector pattern maps to surface C without bypass (reference tenant-tool plan).
5. **Roadmap tension:** `next-directions.md` Tier 1 volume vs capacity — pick next **two** execution epics.
6. **Doc drift process:** Who updates `traceability-matrix.md` when code ships?

---

## 6. Revision history

| Date | Change |
|------|--------|
| 2026-03-27 | Baseline slice §2 closed and archived (`control-plane-product-alignment-baseline-slice-closed.md`); active plan retains §1 + L1–L4. |
| 2026-03-24 | Initial plan: vocabulary, completed doc slice, later phases, discussion agenda. |
