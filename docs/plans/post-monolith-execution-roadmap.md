<!--
File: post-monolith-execution-roadmap.md
Path: docs/plans/post-monolith-execution-roadmap.md
Role: Structured execution plan for work remaining after MOD-REF-001 and enterprise audit phases 1–8 closure.
Used By:
 - Maintainers prioritizing post-refactor slices
 - Agents aligning implementation with strategy + hygiene backlogs
Depends On:
 - docs/plans/enterprise-audit-remediation-plan.md
 - docs/strategy/next-directions.md
 - docs/strategy/traceability-matrix.md
 - docs/plans/tenant-tool-execution-architecture.md
 - .local/index-and-planning/current/work-tracker.md (tracker IDs; path may be gitignored locally)
Notes:
 - Does not replace strategy docs; narrows “what to do next” after modular monolith + audit closure.
 - EA review reconciliation doc slice may land separately in enterprise-audit-remediation-plan.md.
-->

# Post–modular monolith execution roadmap

## 1. Executive snapshot

### 1.1 Closed for the scoped programs

| Program | Status | Evidence / anchor |
|--------|--------|-------------------|
| **MOD-REF-001** (modular monolith) | **Done** (scoped delivery) | Module contracts, `validate_layers`, thin composition root (`AppModules` / bootstrap), trust-boundary services, SQLite audit + migrations, provider-neutral adapter loading, module-aligned tests |
| **Enterprise audit remediation Phases 1–8** | **Closed (plan sense)** | [`enterprise-audit-remediation-plan.md`](enterprise-audit-remediation-plan.md) — includes Phase 8 **defer** (SQLite connection unification documented, not implemented) |
| **Quality bar** | **Enforced** | CI: `pytest` + **`--cov-fail-under=100`** on `src/**` (see `.github/workflows/architecture-fitness.yml`); local parity: `scripts/pr/prepare.py` `GATES` |

### 1.2 Explicitly *not* “everything fixed”

The codebase is positioned as **fit for controlled production / pilot** with correct deployment and ops discipline — **not** “enterprise-by-default at hyperscale.” Remaining themes:

- **Product surface:** northbound **`/v1` OpenAI-compatible gateway**, execution-mode split (`chat` vs `agents`), provider router — see [`next-directions.md`](../strategy/next-directions.md) Tier 1.
- **Operations evidence:** multi-worker / load-SLO profiles, OTLP **collector E2E** — see [`traceability-matrix.md`](../strategy/traceability-matrix.md) and `execution-board-12-gaps.md` (e.g. E04).
- **Boundary debt:** `platform_bootstrap` compat (`_sync_modules_from_state`, `_build_compat_modules_from_state`) — called out in enterprise plan spot-check.
- **Hygiene:** **`COV-100-002`** + **FIND-*** (test layout, docs checklist items) — [`.local/.../work-tracker.md`](../../.local/index-and-planning/current/work-tracker.md).

---

## 2. Guiding principles (all streams)

1. **PR-first:** `feature/` / `fix/` / `chore/` branch → `prepare.py` gates (and governance script when paths require it) → PR → merge workflow artifacts per [`.cursor/rules/pr-workflow-enforcement.mdc`](../../.cursor/rules/pr-workflow-enforcement.mdc).
2. **No adapter-wall bypasses:** provider SDKs and heavy provider logic stay behind runtime adapters; core remains capability + policy driven.
3. **Honest evidence:** prefer CI job names + “verify on branch” over hard-coded test counts in docs ([`enterprise-audit-remediation-plan.md`](enterprise-audit-remediation-plan.md) pattern).
4. **One primary `in_progress` tracker row** in `work-tracker.md` for execution focus.

---

## 3. Workstreams (parallelizable with staffing)

Each stream has **objective**, **suggested slice order**, **acceptance**, and **primary references**.

### Stream A — Test layout & ownership (**COV-100-002** / **FIND-***)

**Objective:** Tests live under `tests/modules/<module>/` with CI and indexes consistent; no long-term home in `tests/modules/unknown/`.

| Step | ID | Action | Acceptance |
|------|-----|--------|------------|
| A.1 | **FIND-001** | Re-home files under `tests/modules/unknown/` to owning module suites; update any CI path references or docs that pointed at `unknown/` | `pytest -q` green; `check_testing_artifacts.py` green; grep shows no stale required paths |
| A.2 | **FIND-004** | Create `tests/modules/integration/`; move host-adapter / cross-layer flow tests (e.g. index-listed `test_host_adapter_input_flow.py` migration) | Tests pass; `test-index.md` / `test-plan.md` updated locally |
| A.3 | **FIND-005** | Create or extend `tests/modules/compliance/` for compliance-owned suites where appropriate; resolve duplication notes vs `tests/modules/audit/` | Same gates; ownership clear in `test-index.md` |
| A.4 | **FIND-006** | Clarify `plugin_contract.py` split intent with docstrings (no behavior change unless required) | `validate_layers` + forbidden-import scan green |
| A.5 | **FIND-007** | Docs maintenance checklist across remaining module docs (enterprise Phase 7 addressed API guide / traceability / `docs/modules/api.md` only partially) | Checklist completed or gaps explicitly deferred with owner |
| A.6 | Optional | **`plugin_contract` / archive** items in `work-tracker.md` (archive research, module-testing-agent scope) | As needed |

**Dependencies:** A.1 before mass renames that confuse blame; A.2/A.3 can follow in separate PRs.

---

### Stream B — `platform_bootstrap` compat reduction (boundary debt)

**Objective:** Reduce reliance on `_sync_modules_from_state` / `_build_compat_modules_from_state` without breaking `app.state` consumers.

| Step | Action | Acceptance |
|------|--------|------------|
| B.1 | Inventory callers and `app.state` fields still populated via compat paths | Short doc section or comment block in service module listing consumers + migration target |
| B.2 | Time-boxed PRs: migrate one consumer group at a time to `AppModules` / explicit facades | No new `getattr(application.state, …)` patterns; existing guard tests pass |
| B.3 | Delete or narrow compat shims when call count hits zero | `validate_layers` + full pytest green |

**References:** [`src/modules/platform_bootstrap/service.py`](../../src/modules/platform_bootstrap/service.py); enterprise plan spot-check row.

---

### Stream C — Northbound API & routing (strategy Tier 1)

**Objective:** Customer-facing OpenAI-compatible surface and governed routing without collapsing the adapter wall.

| Step | Action | Acceptance |
|------|--------|------------|
| C.1 | **Slice design** in [`tenant-tool-execution-architecture.md`](tenant-tool-execution-architecture.md) (or linked addendum): URL map, auth, tenant binding, policy insertion points | Reviewed; no implementation in design-only PR |
| C.2 | **`/v1` gateway** (minimal vertical slice): router mount, contract tests, feature flag / env gate | Tests + docs; core orchestration unchanged in spirit |
| C.3 | **Execution mode split** (`chat` vs `agents`) per adapter strategy | Conformance tests for at least two adapter paths where applicable |
| C.4 | **Provider router** (health / policy-aware) — later tranche | Traceability gap closure recorded with tests |

**Dependencies:** C.1 before C.2; C.2 can ship before C.4.

**References:** [`next-directions.md`](../strategy/next-directions.md) §1; [`interface-strategy.md`](../strategy/interface-strategy.md); [`traceability-matrix.md`](../strategy/traceability-matrix.md).

---

### Stream D — Observability depth (OTel / metrics)

**Objective:** Move from **partial** baseline to **certified** enterprise interoperability where required.

| Step | Action | Acceptance |
|------|--------|------------|
| D.1 | **Collector E2E** in CI or documented manual certification path (docker-compose + assert spans/metrics received) | Traceability / execution-board gap E04 updated |
| D.2 | Expand metric catalog + dashboard hooks as needed | Customer guide + matrix stay honest (“partial” until done) |
| D.3 | Alerting runbooks (correlation ID, sustained `start_session` failures at scale) | Ops doc or runbook path in `docs/operations/` |

**References:** [`customer-api-integration-guide.md`](../api/customer-api-integration-guide.md) §9.2; `execution-board-12-gaps.md` E04.

---

### Stream E — Entitlement & governance ingress (strategy Tier 2)

**Objective:** Tier-aware enforcement and ingress-plane depth per monetization / entitlement matrix.

| Step | Action | Acceptance |
|------|--------|------------|
| E.1 | Map **ENTITLEMENT_MATRIX** claims to enforceable code paths | Traceability row or internal matrix update |
| E.2 | Human approval / `review_required` lifecycle APIs if prioritized | Tests + API docs |
| E.3 | External classifier / signed-plugin depth (tier-gated) | Per `entitlement-matrix` / traceability P1 items |

**References:** [`monetization-strategy.md`](../strategy/monetization-strategy.md); [`entitlement-matrix.md`](../strategy/entitlement-matrix.md).

---

### Stream F — Scale & deployment evidence

**Objective:** Support claims for multi-worker and higher QPS without guessing.

| Step | Action | Acceptance |
|------|--------|------------|
| F.1 | Documented **multi-worker** SQLite / control-state constraints (what is supported vs not) | README or `docs/operations/` |
| F.2 | **Load or soak** scenario (reuse `scripts/perf/` where present) with recorded results | Artifact path referenced from traceability or RC notes |
| F.3 | Revisit SQLite perf only if F.2 shows connect/path as bottleneck | Align with Phase 8 **defer** rationale in [`sqlite.py`](../../src/persistence/adapters/sqlite.py) Notes |

---

## 4. Suggested sequencing (single-team default)

When not parallelizing streams, this order minimizes rework:

1. **A.1 (FIND-001)** — quick hygiene, reduces confusion for all other test work.
2. **B.1–B.2** (compat inventory + first migration) — lowers accidental `app.state` drift.
3. **C.1** design, then **C.2** minimal `/v1` slice — unlocks customer integration narratives.
4. **D.1** collector E2E — high signal for enterprise buyers.
5. **A.2 / A.3** integration + compliance test homes.
6. **E.* / F.*** interleaved by product priority (Tier 2 vs ops).

---

## 5. Gates (every substantive PR)

Run in order per [`scripts/pr/prepare.py`](../../scripts/pr/prepare.py) `GATES`:

1. `python scripts/pr/check_testing_artifacts.py`
2. `python -m pytest -q` (and `pytest --cov=src --cov-fail-under=100` when `src/**` changes)
3. `python scripts/architecture/validate_layers.py`
4. `python scripts/architecture/scan_forbidden_imports.py`

When changing governance, workflow policy, or tracked doc indexes:  
`python scripts/architecture/check_governance_consistency.py`

---

## 6. Tracker discipline

| Artifact | Use |
|----------|-----|
| [`.local/.../work-tracker.md`](../../.local/index-and-planning/current/work-tracker.md) | Exactly one **`in_progress`** row; map streams to **FIND-*** / custom IDs |
| [`.local/.../plan.md`](../../.local/index-and-planning/current/plan.md) | Active slice scope + rollback for the current PR |
| [`.local/.../updates-log.md`](../../.local/index-and-planning/history/updates-log.md) | Post-merge or milestone narrative |
| This file | **Roadmap** only — update when streams complete or priorities shift |

---

## 7. Relation to other plans

| Document | Role |
|----------|------|
| [`enterprise-audit-remediation-plan.md`](enterprise-audit-remediation-plan.md) | **Audit closure** Phases 1–8 + optional EA reconciliation section (other agents) |
| [`tenant-tool-execution-architecture.md`](tenant-tool-execution-architecture.md) | **Option C** execution / gateway sequencing |
| [`next-directions.md`](../strategy/next-directions.md) | **Strategy tiers** — source of *what* matters commercially |
| [`traceability-matrix.md`](../strategy/traceability-matrix.md) | **Gap ↔ code** mapping — update when streams close gaps |

---

## 8. Revision

| Date | Change |
|------|--------|
| 2026-03-24 | Initial roadmap: streams A–F, sequencing, gates, tracker discipline after MOD-REF-001 + audit phase closure. |
