<!--
File: short-long-term-execution-plan.plan.md
Path: docs/plans/short-long-term-execution-plan.plan.md
Role: Implementer-oriented execution companion for short/long horizons; slice checklist and boilerplate aligned with `.cursor/agents/implementer.md`.
Used By:
 - `.cursor/agents/implementer.md` (optional scope source when slice tracks horizon goals)
 - `.local/index-and-planning/current/plan.md` (copy acceptance/rollback from here when relevant)
Depends On:
 - docs/plans/short-long-term-execution-plan.md (canonical horizons + diagrams)
 - docs/strategy/next-directions.md
 - docs/strategy/traceability-matrix.md
 - docs/strategy/interface-strategy.md
 - docs/strategy/entitlement-matrix.md
 - docs/plans/tenant-tool-execution-architecture.md
 - docs/plans/control-plane-product-alignment-plan.md
 - docs/plans/adapter-packages-extraction-handoff.md
 - docs/api/customer-api-integration-guide.md
 - docs/operations/workflow-complete.md (handoff checklist)
Notes:
 - **Does not replace** `.local/index-and-planning/current/plan.md` — that file holds the **single active slice** scope, rollback, and closure checklist per implementation-workflow governance.
 - Keep this file aligned with the canonical horizon doc when themes or tiers shift.
-->

# Implementer plan — short- and long-term horizons

## Governance metadata

| Field | Value |
|-------|--------|
| Status | `active` |
| Owner | `Savin I. Razvan` |
| Version | `1.1.0` |
| Last reviewed | `2026-03-26` |
| Review cadence | `quarterly` (or on canonical [`short-long-term-execution-plan.md`](short-long-term-execution-plan.md) version bump) |
| Canonical narrative | [`short-long-term-execution-plan.md`](short-long-term-execution-plan.md) — purpose, diagrams, short/long themes, horizon × Tier map (section 5) |

---

## How to use this file

1. **Product / priority truth:** [`short-long-term-execution-plan.md`](short-long-term-execution-plan.md) (horizons, diagrams, tier emphasis).
2. **Active slice scope:** [`.local/index-and-planning/current/plan.md`](../../.local/index-and-planning/current/plan.md) — exactly one primary task `in_progress` in [`work-tracker.md`](../../.local/index-and-planning/current/work-tracker.md).
3. **Implementer loop:** [`.cursor/agents/implementer.md`](../../.cursor/agents/implementer.md) + [`.cursor/skills/implementation-execution-loop/SKILL.md`](../../.cursor/skills/implementation-execution-loop/SKILL.md).
4. **Gap bookkeeping:** After architecture-impacting slices, update [`traceability-matrix.md`](../strategy/traceability-matrix.md) per its drift workflow; do not use this companion as the only registry of code/test anchors.

When a slice supports **short-term horizon** goals, pull acceptance themes from **Short-term workstreams** below into `plan.md`. Do **not** expand scope to long-term themes unless [`next-directions.md`](../strategy/next-directions.md) and `plan.md` explicitly promote them.

---

## Non-breaking rules (hard)

Same rules as [short-long-term-execution-plan.md section 2](short-long-term-execution-plan.md); duplicated here so implementers have one file for slice prep.

| Rule | Why |
|------|-----|
| UI never owns policy truth | All policy, gates, guardrails **apply** via control plane APIs; UI sends configuration, core validates and enforces. |
| No SDK/provider imports in core | Adapter work stays in **adapter packages** + contracts; core loads via factory/registry (see [provider-neutral adapter wall](../../.cursor/rules/provider-neutral-adapter-wall.mdc)). |
| Same path for UI and automation | If the main UI can do it, an API client can do it; no hidden admin bypass. |
| Tier claims stay evidence-aligned | Market only **Enforceable** rows in [`entitlement-matrix.md`](../strategy/entitlement-matrix.md) until upgraded. |

---

## Short-term workstreams (pilot proof)

Use these as **epic buckets**; each PR/slice should still be small and reversible. **Primary artifacts** list where to edit or validate first.

### W1 — Core pilot-complete (reference workflow)

| Item | Implementer focus | Evidence |
|------|-------------------|----------|
| Stable turn path | Ingress → orchestration → policy → deterministic tools for **one** reference workflow | Tests + [`tenant-tool-execution-architecture.md`](tenant-tool-execution-architecture.md) status + [short-long-term execution plan section 3 theme 1](short-long-term-execution-plan.md) |
| No bypass for side effects | Documented integration path only; no shadow tool execution | Architecture / integration guide / tests |
| Scope cap | Defer “every gap” — track in [`traceability-matrix.md`](../strategy/traceability-matrix.md) | Slice does not silently widen |

**Primary artifacts:** [`tenant-tool-execution-architecture.md`](tenant-tool-execution-architecture.md) (canonical current state); [`customer-api-integration-guide.md`](../api/customer-api-integration-guide.md) (integration path); `src/api/routers/turns.py`, `src/core/orchestrator.py`, `src/policies/`.

**Suggested tests touchpoints:** `tests/modules/api/`, `tests/modules/policies/`, `tests/modules/core/`.

**Rolling status (docs/tracker — update when slices land):** Horizon cross-link under “Canonical Current State” in `tenant-tool-execution-architecture.md` (STP-W1-001 pattern).

---

### W2 — Governance surfaces + observability

| Item | Implementer focus | Evidence |
|------|-------------------|----------|
| Policy / ingress / guardrails | Tenant APIs + schemas; tier depth per entitlement matrix | API tests + policy tests |
| Observability | Correlation across turn, ingress, tool outcomes via **audit/runtime** APIs | Existing events; extend only with new anchors + tests |
| Main UI (out of repo) | Not implemented here — ensure **only** public APIs are required | No in-repo admin bypass |

**Primary artifacts:** `src/api/routers/tenants.py`, `src/api/routers/runtime_control.py`, [`customer-api-integration-guide.md`](../api/customer-api-integration-guide.md) (policy, quota, §10.0 correlation/audit); [`interface-strategy.md`](../strategy/interface-strategy.md) Layer B.

**Suggested tests touchpoints:** `tests/modules/api/test_slice3_playground.py`, `tests/modules/api/test_audit_api.py`, `tests/modules/policies/`.

**Rolling status:** Customer guide §10.0 correlating turns with audit APIs + cited regression anchors (STP-W2-001 pattern).

---

### W3 — Audit workflow

| Item | Implementer focus | Evidence |
|------|-------------------|----------|
| Query / report | Tenant-scoped audit access as already designed | [`test_audit_api.py`](../../tests/modules/api/test_audit_api.py) patterns |
| Signed export/verify | Enterprise tier only where matrix says Enforceable | Entitlement + audit tests + [`entitlement-matrix.md`](../strategy/entitlement-matrix.md) |

**Primary artifacts:** `src/api/routers/audit.py`, `src/api/schemas/audit_schemas.py`, [`customer-api-integration-guide.md`](../api/customer-api-integration-guide.md) sections 10–11.

**Suggested tests touchpoints:** `tests/modules/api/test_audit_api.py`, `tests/modules/compliance/` when evidence bundles change.

**Rolling status:** Next short-term doc/code slice — align §10.2 operator narrative with Enforceable rows; no claim beyond tests + matrix.

---

### W4 — Adapter SDK + OpenAI reference

| Item | Implementer focus | Evidence |
|------|-------------------|----------|
| Contracts + SDK | PyPI packages isolated; no `src.*` from adapters | [`scripts/packages/external_install_smoke.py`](../../scripts/packages/external_install_smoke.py), `tests/packages/` against installed wheels |
| OpenAI adapter | Register provider → governed turn | Conformance + API smoke (`build_test_app` / playground tests) |
| Handoff doc | Extraction complete; PyPI-only consumption | [`adapter-packages-extraction-handoff.md`](adapter-packages-extraction-handoff.md), [`exo_adapters_pypi_handoff.md`](../handoffs/exo_adapters_pypi_handoff.md) |

**Primary artifacts:** PyPI `exo-brain-core-contracts`, `exo-brain-adapter-sdk`, `exo-adapter-openai`, `exo-adapter-echo` (lockstep **0.1.2**); `src/runtime/` adapter loading; [`next-directions.md`](../strategy/next-directions.md) Tier 1.

**Suggested tests touchpoints:** `tests/modules/runtime/`, `scripts/packages/external_install_smoke.py`, integration tests that register `openai-test` / playground paths.

**Rolling status:** **Shipped (2026-05-29):** extraction complete; eXo-brain PyPI-only; lockstep **0.1.2**. Prior: **STP-W4-003** (contracts **0.1.1+** re-exports), **STP-W4-002** (`runtime_adapter` re-export), **STP-W4-001** (factory dual-check, superseded).

---

### S4 — Main UI platform (out of repo)

Canonical diagram label **Main UI → APIs only** ([short-long-term-execution-plan.md section 1.1](short-long-term-execution-plan.md)): the company main UI consumes **REST / SSE / WebSocket** (and optional `/v1` where enabled). It must not implement parallel enforcement.

**Primary artifacts:** [`interface-strategy.md`](../strategy/interface-strategy.md); [`governed-execution-positioning.md`](../strategy/governed-execution-positioning.md); [`control-plane-product-alignment-plan.md`](control-plane-product-alignment-plan.md).

**Implementer check:** No new “admin shortcut” routes in this repo that skip policy middleware or tenant scope.

---

## Long-term (do not fold into short-term slices by default)

Promote only when [`short-long-term-execution-plan.md`](short-long-term-execution-plan.md) **section 4** and [`next-directions.md`](../strategy/next-directions.md) are explicitly updated. See also **section 5** (horizon × Tier map) in the canonical file.

Themes (summary only — detail stays canonical):

- Full adapter ecosystem, certification automation, provider router depth.
- Commercial plan / subscription source of truth / metering (typically outside or beside core slices).
- Enterprise-only depth: approval workflows, external plugin ingestion, token/cost governance, MCP policy depth, compliance waves.
- Optional in-repo console.

---

## Slice boilerplate (copy into `.local/.../current/plan.md`)

```markdown
## Slice (horizon: short-term | long-term)

**Tracks:** docs/plans/short-long-term-execution-plan.md — Workstream W_

### Scope
- …

### Acceptance criteria
- …

### Rollback
- …

### Modules / paths (expected)
- …

### Tests
- … (see tests/modules/...)

### Gates
- Run `scripts/pr/prepare.py` GATES; add `check_governance_consistency.py` if governance/docs/workflows changed.

### Closure
- work-tracker.md, updates-log.md, test-index/test-plan if tests moved; coverage-index if coverage slice.
```

---

## Implementer checklists

### Before starting a horizon-tagged slice

- [ ] Read `.local/.../current/plan.md` and `work-tracker.md` (one primary `in_progress`).
- [ ] Confirm slice maps to **W1–W4** or is explicitly a **long-term** promotion in strategy docs.
- [ ] Confirm scope does not violate **Non-breaking rules** above.
- [ ] Copy or refresh the **Slice boilerplate** block into `plan.md` with real scope, acceptance, rollback.

### Before handoff / PR

- [ ] Run `scripts/pr/prepare.py` **GATES**; add `scripts/architecture/check_governance_consistency.py` when governance, workflows, or tracked policy docs changed.
- [ ] Append `.local/.../history/updates-log.md`; update `work-tracker.md` (and **Rolling status** rows in this file when a workstream milestone is doc-only or clearly complete).
- [ ] If tests or ownership moved: `test-plan.md`, `test-index.md`; if coverage slice: regenerate `coverage-index.md` per `plan.md` / [`workflow-complete.md`](../operations/workflow-complete.md).

---

## Review cadence

After a milestone slice:

1. Confirm this companion still matches [`short-long-term-execution-plan.md`](short-long-term-execution-plan.md) and [`next-directions.md`](../strategy/next-directions.md).
2. If the canonical horizon doc changes, update **W1–W4** tables and **Rolling status** rows here.
3. Bump **Version** / **Last reviewed** in **Governance metadata** when you materially edit workstreams or checklists.
