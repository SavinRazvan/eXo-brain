<!--
File: README.md
Path: docs/strategy/README.md
Role: Index and reading order for strategic architecture goals and execution guardrails.
Used By:
 - AGENTS.md
 - docs/README.md
 - docs/plans/docs-inventory-master.md
Depends On:
 - docs/plans/tenant-tool-execution-architecture.md
 - docs/plans/control-plane-product-alignment-plan.md
Notes:
 - Keep synchronized when adding or retiring docs/strategy documents.
 - Last reviewed: 2026-05-29
-->

# Strategy documentation

## Governance metadata

| Field | Value |
|-------|-------|
| **Status** | `active` |
| **Owner** | Savin I. Razvan |
| **Version** | `2.0.0` |
| **Last reviewed** | `2026-05-29` |
| **Review cadence** | Monthly (or on architecture-impacting slices) |

## Purpose

Strategic documents define product direction, non-negotiable boundaries, monetization posture, and traceability to code/tests. They prevent direction drift while implementation evolves.

**Canonical product model:** eXo-brain is the **control plane** for governed execution; **monetization targets safety and governance**, not raw model resale. **Repository boundary:** this repo is **control plane only** — adapter packages live in **[SavinRazvan/eXo_adapters](https://github.com/SavinRazvan/eXo_adapters)** (PyPI). See **Repository boundary** in [`governed-execution-positioning.md`](governed-execution-positioning.md).

**Integration surfaces:** provider runtime adapters (southbound), control plane API (`/tenants/...` + global routes — [customer-api-integration-guide.md](../api/customer-api-integration-guide.md)), optional customer bridge `POST /v1/chat/completions`. Executable cross-cutting plan: [`control-plane-product-alignment-plan.md`](../plans/control-plane-product-alignment-plan.md).

## Reading order

| # | Document | Role |
|---|----------|------|
| 1 | [goal.md](goal.md) | North star, problems solved, platform boundary |
| 2 | [core.md](core.md) | Core invariants and non-bypassable governance |
| 3 | [adapter-strategy.md](adapter-strategy.md) | Adapter ecosystem, lanes, certification |
| 3b | [adapter-compatibility-matrix.md](adapter-compatibility-matrix.md) | **Published PyPI 0.1.2**, semver, M0 status |
| 4 | [monetization-strategy.md](monetization-strategy.md) | Tiers, value capture, governance monetization |
| 5 | [governed-execution-positioning.md](governed-execution-positioning.md) | ICP, messaging guardrails, four-layer model |
| 6 | [entitlement-matrix.md](entitlement-matrix.md) | Feature ↔ tier ↔ enforcement ↔ tests |
| 7 | [compliance-profile-matrix.md](compliance-profile-matrix.md) | Compliance waves and evidence mapping |
| 8 | [deployment-models.md](deployment-models.md) | Deployment packaging and support boundaries |
| 9 | [interface-strategy.md](interface-strategy.md) | API-first posture; Layer A/B; UI deferred |

**Self-serve governance spine** (after interface strategy when building onboarding or policy UX):

| Document | Role |
|----------|------|
| [customer-self-serve-governance-journey.md](customer-self-serve-governance-journey.md) | Product contract, journey stages, agent rules |
| [foundation-tier-adoption-checklist.md](foundation-tier-adoption-checklist.md) | Minimal Foundation API path |
| [governance-configuration-reference-model.md](../plans/governance-configuration-reference-model.md) | Config entities, precedence, UI mapping |
| [customer-api-integration-guide.md](../api/customer-api-integration-guide.md) | **Wire-level** endpoints and examples |
| [governed-execution-pipeline.md](../architecture/governed-execution-pipeline.md) | Canonical turn ordering |
| **Planned in-tree:** `docs/api/governance-preview-and-testing.md`, `docs/operations/governance-reason-code-catalog.md` |

| # | Document | Role |
|---|----------|------|
| 10 | [traceability-matrix.md](traceability-matrix.md) | Decision → code → test anchors; known gaps |
| 11 | [next-directions.md](next-directions.md) | Prioritized implementation directions |
| 12 | [execution-board-12-gaps.md](execution-board-12-gaps.md) | Phased board for 12 priority gaps |

**Horizons:** [short-long-term-execution-plan.md](../plans/short-long-term-execution-plan.md) (pilot vs platform maturity; main UI as API consumer).

## Document index (all files)

| File | Topic |
|------|--------|
| [goal.md](goal.md) | Product goals |
| [core.md](core.md) | Core strategy |
| [adapter-strategy.md](adapter-strategy.md) | Adapter ecosystem |
| [adapter-compatibility-matrix.md](adapter-compatibility-matrix.md) | Versions and certification table |
| [monetization-strategy.md](monetization-strategy.md) | Monetization |
| [governed-execution-positioning.md](governed-execution-positioning.md) | Positioning |
| [entitlement-matrix.md](entitlement-matrix.md) | Entitlements |
| [compliance-profile-matrix.md](compliance-profile-matrix.md) | Compliance |
| [deployment-models.md](deployment-models.md) | Deployment |
| [interface-strategy.md](interface-strategy.md) | Interfaces |
| [customer-self-serve-governance-journey.md](customer-self-serve-governance-journey.md) | Self-serve journey |
| [foundation-tier-adoption-checklist.md](foundation-tier-adoption-checklist.md) | Foundation adoption |
| [traceability-matrix.md](traceability-matrix.md) | Traceability |
| [next-directions.md](next-directions.md) | Next directions |
| [execution-board-12-gaps.md](execution-board-12-gaps.md) | 12-gap execution board |

## Update policy

- Update strategy docs before or alongside architecture-impacting slices.
- Keep boundaries aligned with `AGENTS.md` and [`tenant-tool-execution-architecture.md`](../plans/tenant-tool-execution-architecture.md).
- Refresh [traceability-matrix.md](traceability-matrix.md) when decisions, routes, or tests change.
- Sync [entitlement-matrix.md](entitlement-matrix.md) when tier gates move.
- Run `python scripts/architecture/check_governance_consistency.py` when this index or tracked policy docs change.

## Scope boundaries

- Strategy defines **what** and **why**; implementation contracts live in [`docs/modules/`](../modules/README.md) and [`docs/api/`](../api/README.md).
- Operational runbooks: [`docs/operations/`](../operations/README.md).

## Closure snapshot (baseline shipped vs planned)

**Shipped (representative):** control plane API with governed turns (SSE/WS), ingress gate chain, entitlements middleware, policy templates, packaged adapters on **PyPI 0.1.2**, optional `/v1` gateway, customer integration guide v1.9+, notebooks smoke path, partial OTLP/Prometheus export.

**Still planned / depth backlog:** customer bridge SDK, universal Lane A adapter package, runtime provider router, human approval action APIs, governance simulation API, MCP policy depth on default paths, token-aware inference budgets, deployment certification automation, full compliance packaging. Details: [traceability-matrix.md](traceability-matrix.md) §3, [next-directions.md](next-directions.md).
