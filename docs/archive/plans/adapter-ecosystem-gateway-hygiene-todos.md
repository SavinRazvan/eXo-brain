<!--
File: adapter-ecosystem-gateway-hygiene-todos.md
Path: docs/archive/plans/adapter-ecosystem-gateway-hygiene-todos.md
Role: Checkbox execution checklist for adapter ecosystem, northbound gateway, and hygiene phases (maps to EA/FIND IDs).
Used By:
 - Maintainers executing slices from adapter-ecosystem-gateway-hygiene-plan.md
Depends On:
 - docs/archive/plans/adapter-ecosystem-gateway-hygiene-plan.md
 - docs/archive/plans/post-monolith-execution-roadmap.md
 - .local/index-and-planning/current/work-tracker.md
Notes:
 - Decisions: EA-001 = P0-A (Python 3.12+); EA-002 = 1b (four GATES in prepare.py; conditional governance documented).
-->

# Adapter ecosystem / gateway / hygiene — execution checklist

> **Archived** (checkbox snapshot). Canonical replacement: same as `adapter-ecosystem-gateway-hygiene-plan.md`. Archived on: 2026-03-25.

## 0. Sequencing

Follow the ordered phases in [adapter-ecosystem-gateway-hygiene-plan.md §11](adapter-ecosystem-gateway-hygiene-plan.md#11-suggested-sequencing-single-team) (Phase 0 → 1 → 2.1 → …). This file is the granular checkbox view; narrative and acceptance criteria stay in the main plan.

---

## Phase 0 — EA-001 (P0-A: Python 3.12+)

- [x] **AGE-P0-01** — Inventory `python-version` / Python mentions: `.github/workflows/*.yml`, `requirements.txt`, `README.md`, `Dockerfile`, contributor snippets under `docs/`.
- [x] **AGE-P0-02** — Single stated minimum (**3.12+**) in `requirements.txt` header; document newer CPython (e.g. 3.13) as expected compatible unless noted.
- [x] **AGE-P0-03** — README: short **Supported Python** line (CI version + local venv parity).
- [x] **AGE-P0-04** — Confirm CI jobs that run tests/lint use **3.12** consistently; no unexplained 3.13 vs 3.12 split.
- [x] **AGE-P0-05** — Run `python -m pytest -q --cov=src --cov-fail-under=100` on **3.12** after edits; record outcome in PR / `updates-log.md` when used for the slice.

---

## Phase 1 — EA-002 (1b: gate docs)

- [x] **AGE-P1-01** — README: authoritative merge prep order = `scripts/pr/prepare.py` `GATES` (four commands); **separate** bullet/step for `check_governance_consistency.py` when paths touch governance (align with `.cursor/rules/pr-workflow-enforcement.mdc`).
- [x] **AGE-P1-02** — `AGENTS.md`: same split (no implied “five default gates” without clarifying conditional).
- [x] **AGE-P1-03** — Grep `.agents/skills/`, `.cursor/skills/` for duplicate gate lists; align or “see `prepare.py` `GATES`” (spot-check; no drift vs 1b).
- [ ] **AGE-P1-04** — *If switching to option 1a:* append governance to `GATES` in `prepare.py` and update docs to “five gates” everywhere (**not chosen** — 1b locked).

---

## Phase 2 — Test layout (FIND-001 / 004 / 005 / 006; EA-003 / 004)

- [x] **AGE-P2-01 (FIND-001)** — List `tests/modules/unknown/` files; assign each to `tests/modules/<owner>/`; move; fix imports.
- [x] **AGE-P2-02** — `rg unknown` on `.github/`, `docs/`, `scripts/pr/check_testing_artifacts.py` if applicable; update stale paths.
- [x] **AGE-P2-03** — Update `.local/index-and-planning/test-index.md` and `test-plan.md` (paths may be gitignored locally).
- [x] **AGE-P2-04** — `check_testing_artifacts.py` + `pytest -q` (+ coverage if `src/**` touched).
- [x] **AGE-P2-05 (FIND-004)** — Add `tests/modules/integration/` package; move host-adapter / cross-layer tests per tracker; re-run gates.
- [x] **AGE-P2-06 (FIND-005)** — Resolve compliance vs audit test home per tracker; move `evidence_bundle` (or related) suites; update indexes.
- [x] **AGE-P2-07 (FIND-006)** — Docstring-only clarification for `plugin_contract.py` split (`src/agents/` vs `src/tools/plugins/`); no behavior change unless required.

---

## Phase 3 — Adapter platform (EA-006 / EA-007)

- [x] **AGE-P3-01** — Add **compatibility matrix** (per package: `exo-brain-core-contracts`, `exo-brain-adapter-sdk`, `exo-adapter-openai`, `exo-adapter-echo`) in `docs/strategy/adapter-strategy.md` or linked `docs/strategy/adapter-compatibility-matrix.md`.
- [x] **AGE-P3-02** — Document **semver rules** for contracts (major/minor/patch) consistent with `packages/exo-brain-core-contracts/.../runtime_adapter.py` “v1 compatibility” note.
- [x] **AGE-P3-03** — Ops/runbook snippet: recommended log dimensions (`provider_id`, adapter package version, contracts version, `api_type`) in `docs/operations/` or strategy cross-link.
- [x] **AGE-P3-04** — **M0 gap check:** compare `docs/strategy/adapter-strategy.md` M0 acceptance to current code; document **done** vs **remaining** with test anchors.
- [x] **AGE-P3-05** — **Lane A (optional slice):** spike HTTP OpenAI-compatible adapter package **or** explicit defer note in matrix with owner.
- [x] **AGE-P3-06** — **Conformance / CI:** ensure `tests/packages/` (and/or new job) runs on `packages/**` changes; pin contracts version in doc or lockfile story.
- [x] **AGE-P3-07 (EA-007)** — Contributor doc: run `scripts/packages/external_install_smoke.py` when touching `packages/**`; verify CI path filters.

---

## Phase 4 — Northbound `/v1` (EA-005)

- [x] **AGE-P4-01** — Design PR: addendum (in `docs/plans/tenant-tool-execution-architecture.md` Slice 5 or `docs/archive/plans/northbound-v1-gateway.md`): URL map, auth→tenant binding, middleware/gate order (reference `src/api/routers/turns.py`), explicit non-goals (no raw upstream proxy).
- [x] **AGE-P4-02** — Link design from `docs/architecture/ARCHITECTURE.md` and/or `docs/api/customer-api-integration-guide.md`.
- [x] **AGE-P4-03** — Implement FastAPI router under `src/api/` with **feature flag** / env gate.
- [x] **AGE-P4-04** — Tests: success, **401/403**, **policy denial** (prove no governance bypass).
- [x] **AGE-P4-05** — Reuse existing turn/orchestration pipeline (no second tool-execution path).
- [x] **AGE-P4-06** — Customer guide: supported endpoints + limitations; update `docs/strategy/traceability-matrix.md` when slice closes.

---

## Phase 5 — Portfolio (after 3 + 4 MVP)

- [x] **AGE-P5-01** — Prove Lane A with **two** distinct `base_url` configs in tests.
- [x] **AGE-P5-02** — Add matrix row + certification evidence before “GA” claims per provider.

---

## Optional hygiene

- [x] **AGE-OPT-01** — Reduce PyJWT `InsecureKeyLengthWarning` noise: ≥32-byte secrets in JWT tests or scoped `pytest.mark.filterwarnings`.

---

## Crosswalk

| TodoID | EA / FIND | Primary files / areas |
|--------|-----------|------------------------|
| AGE-P0-* | **EA-001** | `requirements.txt`, `.github/workflows/*.yml`, `README.md`, `Dockerfile` |
| AGE-P1-* | **EA-002** | `README.md`, `AGENTS.md`, `.agents/skills/`, `.cursor/skills/`, `scripts/pr/prepare.py` (if 1a) |
| AGE-P2-01–04 | **FIND-001**, **EA-003** | `tests/modules/pr_workflow/`, `architecture_scripts/`, `release_scripts/`, `perf_scripts/`, `test-index.md`, `check_testing_artifacts.py` |
| AGE-P2-05 | **FIND-004**, **EA-004** | `tests/modules/integration/` |
| AGE-P2-06 | **FIND-005** | `tests/modules/compliance/`, evidence bundle suites |
| AGE-P2-07 | **FIND-006** | `src/agents/`, `src/tools/plugins/`, `plugin_contract.py` |
| AGE-P3-* | **EA-006**, **EA-007** | `docs/strategy/adapter-strategy.md`, `packages/`, `tests/packages/` |
| AGE-P4-* | **EA-005** | `src/api/`, tenant-tool plan, customer API guide |
| AGE-P5-* | Portfolio | Lane A tests, certification matrix |
| AGE-OPT-01 | Hygiene | JWT test fixtures |
