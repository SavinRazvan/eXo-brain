<!--
File: README.md
Path: docs/strategy/README.md
Role: Index and reading order for strategic architecture goals and execution guardrails.
Used By:
 - goal.md
 - core.md
 - adapter-strategy.md
 - monetization-strategy.md
 - governed-execution-positioning.md
 - entitlement-matrix.md
 - compliance-profile-matrix.md
 - deployment-models.md
 - interface-strategy.md
 - traceability-matrix.md
 - next-directions.md
 - execution-board-12-gaps.md
Depends On:
 - AGENTS.md
 - docs/plans/tenant-tool-execution-architecture.md
Notes:
 - Keep this index synchronized when adding or retiring docs/strategy documents.
-->

# Architecture Goals Index

## Governance Metadata

- Status: `active`
- Owner: `Savin I. Razvan`
- Version: `1.8.1`
- Last Reviewed: `2026-03-25`
- Review Cadence: `monthly`
- Decision Scope: `Folder-level indexing, reading order, and strategy document governance for docs/strategy.`

## Purpose

This folder contains strategic documents that define product direction, non-negotiable boundaries, monetization posture, and operational traceability.

These documents are intended to prevent direction drift while implementation evolves.

**Canonical product model (2026-03-24):** eXo-brain is the **control plane** for governed execution; **monetization targets safety and governance**, not raw model resale. **Repository boundary:** the **eXo-brain repository** is **control plane only** (non-monorepo for adapters); adapter packages/SDK target **separate repos** — see **Repository boundary** in `governed-execution-positioning.md`. **North star** (AI as governed infrastructure; startups/orgs ship faster with API-enforced policy and audit) and the **enterprise four-layer separation of concerns** live in the same file. Unambiguous **integration surfaces** (provider runtime adapter outbound, control plane API, customer bridge including optional `/v1` and a future thin SDK) are defined there and in `goal.md` (section 5a). Executable cross-cutting plan: [`docs/plans/control-plane-product-alignment-plan.md`](../plans/control-plane-product-alignment-plan.md).

## Reading Order

1. `goal.md`  
   Product north-star, problems solved, and platform boundary.
2. `core.md`  
   Core invariants, governance enforcement, and safety-critical architecture decisions.
3. `adapter-strategy.md`  
   Adapter ecosystem strategy, packaging, certification, and fallback behavior.  
   **Companion:** `adapter-compatibility-matrix.md` (semver, published package versions, M0/Lane A status).
4. `monetization-strategy.md`  
   Monetization model, tier boundaries, and value capture strategy.
5. `governed-execution-positioning.md`
   Product definition, ICP focus, monetization boundary, and messaging guardrails.
6. `entitlement-matrix.md`  
   Feature-to-tier enforcement and evidence matrix for monetization operability.
7. `compliance-profile-matrix.md`  
   Phased compliance-readiness profiles and control/evidence mapping.
8. `deployment-models.md`  
   Deployment packaging and support boundaries by model and tier.
9. `interface-strategy.md`  
   API-first experience strategy and UI roadmap constraints.
10. `traceability-matrix.md`  
   Decision-to-code and decision-to-test mapping for drift detection.
11. `next-directions.md`  
    Architecture-aligned priorities and next implementation slices. **Companion:** [`docs/plans/short-long-term-execution-plan.md`](../plans/short-long-term-execution-plan.md) — short vs long horizons, main UI as API consumer, diagrams (mirrored in root `README.md`).
12. `execution-board-12-gaps.md`
    Execution-ready implementation board for the 12 agreed priority gaps (phases, epics, tests, rollback).

## Update Policy

- Update strategic docs before or alongside architecture-impacting implementation slices.
- Keep boundaries aligned with `AGENTS.md` and canonical operational plans.
- Use `traceability-matrix.md` to verify each strategic decision still maps to concrete code/tests/APIs.

## Change Control Rule

- Any architecture-impacting strategy change must update:
  - the affected strategy doc(s),
  - `traceability-matrix.md`,
  - this index when document set or reading order changes.
- If there is uncertainty, mark the section as `Draft Decision` with owner and review date instead of leaving ambiguity.

## Scope Boundaries

- These documents define strategy and constraints.
- Detailed implementation contracts remain in module docs under `docs/modules/`.
- Operational runbooks remain under `docs/operations/`.

## Closure Snapshot (2026-03-12; product vocabulary 2026-03-24)

Now enforceable in strategy package:
- governance metadata standardization across all docs/strategy docs,
- entitlement matrix with enforceable vs planned capability flags,
- compliance profile matrix with phased wave model,
- deployment model strategy with support and tier posture,
- cross-document traceability anchors.
- **2026-03-24:** Canonical **control plane** + **integration surfaces** (provider runtime adapter, control plane API, customer bridge) documented across `docs/strategy/*`, `docs/plans/control-plane-product-alignment-plan.md`, `docs/architecture/ARCHITECTURE.md`, and `docs/architecture/workspace-architecture.md`.

Still planned (not yet fully implemented in product controls):
- adapter portfolio expansion execution across universal/native/service lanes with certification evidence automation,
- runtime provider router depth (health/cost/policy-aware routing decisions),
- advanced external classifier-routing depth and external signed-plugin package ingestion depth (baseline gate chain + profile/custom-rule/classifier shadow-enforce controls + signed plugin lifecycle baseline + policy-template/risk-profile APIs + entitlement hard-gating are implemented),
- first-class approval action workflow for review-required escalation outcomes,
- token-aware inference budget governance and MCP policy-depth controls (per-server tool filtering + credential scope policy),
- deeper governance runtime diagnostics over profile-specific SLO baselines (profile-aware thresholds + per-profile release reporting are implemented),
- deployment certification path for private/self-hosted support,
- expanded compliance artifact catalog and profile-specific runbooks.

For architecture-aligned next directions and slice priorities, see `next-directions.md`.
For implementation sequencing and acceptance details for the 12 priority gaps, see `execution-board-12-gaps.md`.
