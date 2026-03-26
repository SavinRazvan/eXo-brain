<!--
File: adapter-ecosystem-gateway-hygiene-plan.md
Path: docs/archive/plans/adapter-ecosystem-gateway-hygiene-plan.md
Role: Detailed phased plan for adapter ecosystem (versioned, provider-neutral), northbound /v1 gateway, and platform hygiene after enterprise audit + local verification.
Used By:
 - Maintainers and implementers scoping PRs
 - Alignment with docs/strategy/adapter-strategy.md and tenant-tool Slice 5
Depends On:
 - docs/archive/plans/post-monolith-execution-roadmap.md (umbrella streams A–F)
 - docs/plans/tenant-tool-execution-architecture.md (Option C Slice 5)
 - docs/strategy/goal.md, docs/strategy/next-directions.md
 - .local/workflow-artifacts/enterprise-architecture-audit/enterprise-audit-actions.md (EA-IDs)
 - .local/index-and-planning/current/work-tracker.md (FIND-*, COV-100-002)
Notes:
 - Re-verify pytest counts on your branch; numbers drift as tests are added.
 - PR-first; one primary in_progress row in work-tracker.md per governance rules.
-->

# Adapter ecosystem, northbound gateway, and hygiene — detailed execution plan

> **Archived** (detailed phased checklist). Canonical replacement: `docs/strategy/adapter-strategy.md`, `docs/strategy/next-directions.md`, `docs/plans/adapter-packages-extraction-handoff.md`, `docs/plans/short-long-term-execution-plan.md`. Archived on: 2026-03-25.

## 1. Purpose

Turn **audit findings**, **strategy tiers**, and **verified local quality evidence** into **sequenced, PR-sized work** with explicit acceptance criteria. This plan **details** themes that appear at stream level in [`post-monolith-execution-roadmap.md`](post-monolith-execution-roadmap.md) (especially Streams **A**, **C**, and adapter breadth) and maps them to **EA-*** and **FIND-*** trackers.

**Out of scope here:** full Tier 2 entitlement depth, collector E2E (see roadmap Streams **E**, **D**).

---

## 2. Evidence baseline (quality bar — verified)

**Recorded run (local `.venv`, Linux):**

```bash
python -m pytest -q --cov=src --cov-report=term-missing --cov-fail-under=100
```

**Outcome:** **1180 passed**, **1 skipped** (soak suite behind `EXO_RUN_SOAK_TESTS`), **100%** line coverage on `src/**`, **Python 3.12.3** (platform line in pytest output).

**Implications:**

1. The **enterprise audit “Medium confidence”** note (pytest not run on audit host) is **superseded** for this tree state: full suite + coverage gate **green** on **3.12**.
2. **EA-001 (Python version drift)** should be resolved by **explicitly choosing** a canonical minimum that matches **proven** CI + local (see Phase 0).
3. Residual **PyJWT `InsecureKeyLengthWarning`** noise in tests is **test-only short keys** — optional follow-up: suppress in fixtures or use ≥32-byte test secrets for cleaner logs (not a plan phase unless you want it).

---

## 3. Strategic anchors (what “done” means)

| Theme | Source | Implementation north star |
|--------|--------|---------------------------|
| Provider-neutral core | `goal.md`, `provider-neutral-adapter-wall.mdc` | Orchestration depends on **`RuntimeAdapter`** + contracts, not provider SDKs. |
| Versioned adapter plane | `docs/strategy/adapter-strategy.md` | **`exo-brain-core-contracts`** semver; **`exo-brain-adapter-sdk`** tracks supported contract range; each **`exo-adapter-*`** declares contract + SDK + provider dependency matrix. |
| Northbound compatibility | `next-directions.md` Tier 1, `tenant-tool-execution-architecture.md` Slice 5 | **`/v1`-style** surface for OpenAI clients; **same governance spine** as tenant/session APIs (ingress, policy, deterministic tools). |
| Two provider lanes | `adapter-strategy.md` | **Lane A:** OpenAI-compatible HTTP (many providers). **Lane B:** native/hybrid when Lane A is insufficient. |

**Existing packages (confirmed in tree):** `packages/exo-brain-core-contracts`, `packages/exo-brain-adapter-sdk`, `packages/exo-adapter-openai`, `packages/exo-adapter-echo` + conformance tests under `tests/packages/`.

---

## 4. Phase 0 — Canonical Python version (EA-001) — **decision + one PR**

**Problem:** `requirements.txt` header says **Python 3.13+**; CI **architecture-fitness** uses **Python 3.12**; local proof is **3.12.3**.

**Options (pick one; document the other as unsupported or secondary):**

| Option | Action | When to choose |
|--------|--------|----------------|
| **P0-A (recommended default)** | Set canonical minimum to **3.12+**: update `requirements.txt` header (and any contributor docs) to match **CI + proven venv**; add one line in `README.md` “Supported: 3.12.x (CI), 3.13+ expected compatible unless noted.” | You want **one** truth that matches today’s green CI and your last full coverage run. |
| **P0-B** | Move **CI** to **3.13** (matrix or single version) and keep `requirements.txt` as 3.13+; re-run full pytest + coverage on 3.13 in CI. | You **require** 3.13-only language/stdlib features. |

**Acceptance:**

- [x] Single documented **minimum Python** in `requirements.txt`, `README.md`, and **CI workflow** `python-version` aligned (no silent mismatch).
- [x] `python -m pytest -q` and (for `src/**` changes) `--cov=src --cov-fail-under=100` green on the **chosen** CI version.

**Tracker:** **EA-001** → close or move to `done` in `work-tracker.md` when merged.

**Effort:** Low · **Risk:** Low

---

## 5. Phase 1 — Merge gate narrative vs `prepare.py` (EA-002) — **one small PR**

**Problem:** [`scripts/pr/prepare.py`](../../scripts/pr/prepare.py) `GATES` lists **four** commands; `README.md` / `AGENTS.md` still describe **five** when including `check_governance_consistency.py`.

**Options:**

| Option | Action |
|--------|--------|
| **1a** | Append `check_governance_consistency.py` to `GATES` so **every** prepare runs governance (stricter, slower PRs). |
| **1b** | Keep **four** gates; edit `README.md` / `AGENTS.md` to state: “Prepare runs `GATES`; **also** run `check_governance_consistency.py` when changing governance, `.cursor/`, `.agents/`, or tracked policy docs (CI mirrors path filters).” |

**Acceptance:**

- [x] No contradictory “these are the merge gates” lists; **single SoT** is `prepare.py` for default prepare order.
- [x] `AGENTS.md` and README match chosen option.

**Tracker:** **EA-002**

**Effort:** Low

---

## 6. Phase 2 — Test layout hygiene (EA-003, EA-004, EA-005 partial) — **1–3 PRs**

Aligns with roadmap **Stream A** and tracker **FIND-001**, **FIND-004**, **FIND-005**, **FIND-006**.

| Step | ID | Work | Acceptance |
|------|-----|------|------------|
| 2.1 | **FIND-001** / **EA-003** | Re-home `tests/modules/unknown/` → owning `tests/modules/<module>/`; fix any CI/doc path assumptions | `pytest -q` green; `check_testing_artifacts.py` green; `test-index.md` updated |
| 2.2 | **FIND-004** / **EA-004** | Add `tests/modules/integration/`; move cross-layer tests (e.g. host adapter flows) per tracker | Same gates; ownership clear in `test-index.md` |
| 2.3 | **FIND-005** | Normalize compliance vs audit test homes per tracker (avoid duplicate ownership confusion) | Same gates |
| 2.4 | **FIND-006** | Docstring-only clarification on `plugin_contract.py` split where needed | `validate_layers` + forbidden imports green |

**Suggested order:** 2.1 first (reduces confusion for all later test PRs).

**Effort:** Moderate (mostly moves + index updates)

---

## 7. Phase 3 — Adapter ecosystem platform (EA-006) — **multiple PRs**

**Objective:** Core stays stable when **provider APIs churn**; adapters ship on **their own semver** with explicit **contract compatibility**.

### 3.1 Documentation & policy (no runtime change)

| Task | Output | Acceptance |
|------|--------|------------|
| **Compatibility matrix** | `docs/` page (or section in `adapter-strategy.md`): for each published adapter, rows for **core-contracts** range, **adapter-sdk** range, **provider SDK** / API profile | Reviewed; linked from `README.md` or strategy index |
| **Versioning rules** | Explicit **semver rules** for `exo-brain-core-contracts` (breaking = major; additive events = minor) | Matches code comment in `runtime_adapter.py` (“v1 compatibility”) |
| **Observability dimensions** | Runbook or doc: log/metric fields **`adapter_package_version`**, **`contracts`**, **`api_type`**, **`provider_id`** | Operators can diagnose “provider broke” vs “core broke” |

### 3.2 Registration & protocol typing

| Task | Output | Acceptance |
|------|--------|------------|
| **`api_type` completion** | Per `adapter-strategy.md` M0: registry + API schemas treat protocol as **explicit** (`openai_native`, `openai_compatible`, `custom`, …) | Tests for default/backward compatibility when field omitted |
| **Lane A baseline package** (optional slice) | New `exo-adapter-openai-compatible` or extend pattern in existing package: **HTTP** OpenAI-compatible path shared by multiple providers | `external_install_smoke.py` green; no `src.*` imports in package |

### 3.3 Certification automation

| Task | Output | Acceptance |
|------|--------|------------|
| **Conformance gate** | CI job or script: each adapter runs **echo-level** or **contract** tests against **pinned** `exo-brain-core-contracts` | Fails if adapter drifts from contract |
| **EA-007** | When touching `packages/**`, run [`scripts/packages/external_install_smoke.py`](../../scripts/packages/external_install_smoke.py) locally; ensure CI already covers or add path filter | Document in contributor flow |

**Tracker:** **EA-006**, **EA-007**; defer rows in `work-tracker.md` (“Adapter artifact signature enforcement”) may fold into 3.3.

**Effort:** High (spread across weeks) · **Dependencies:** Phase 0–1 stable (fewer environment surprises)

---

## 8. Phase 4 — Northbound OpenAI-compatible `/v1` gateway (EA-005) — **design PR then vertical slice**

**Objective:** External apps use familiar OpenAI client shapes; **internal** execution still goes through **ingress + policy + deterministic tool** paths.

Aligns with **tenant-tool-execution-architecture.md** “Option C Next-Phase Slice 5” and roadmap **Stream C**.

### 4.1 Design (C.1) — **PR: docs + OpenAPI sketch only**

Deliverables:

- **URL map:** e.g. mount prefix `/v1` vs separate app; which routes in v1 (chat completions, models, …) — **minimal first**.
- **Auth & tenant binding:** API key → tenant/session mapping; must **not** introduce a governance bypass.
- **Policy insertion points:** same middleware/gate order as existing turn routers (cite `src/api/routers/turns.py` / ingress wiring).
- **Explicit non-goals:** v1 is not a raw pass-through proxy to OpenAI’s API.

**Acceptance:** Reviewed in PR; linked from `docs/architecture/ARCHITECTURE.md` or customer guide appendix.

### 4.2 Minimal implementation (C.2) — **PR: feature-flagged router**

Deliverables:

- FastAPI router under **`src/api/`** (path strings may include `/v1/...`).
- **Env or setting gate** (default off in prod if you need conservative rollout).
- Contract tests: **happy path + auth failure + policy denial** (prove bypass impossible).
- Map request → existing orchestration/session pipeline (reuse host adapter / turn execution — **no duplicate tool execution** paths).

**Acceptance:**

- [ ] `pytest -q` + coverage gate green for `src/**` edits.
- [ ] `validate_layers` + `scan_forbidden_imports` green.
- [ ] Customer-facing note in `docs/api/customer-api-integration-guide.md` (scope + limitations).

### 4.3 Follow-ups (later PRs)

- **Execution mode split** (`chat` vs `agents` vs `workflow`) per strategy — **after** 4.2 stable.
- **Provider router** (health/cost/policy) — roadmap Stream C.4; depends on observability inputs.

**Tracker:** **EA-005**; update `traceability-matrix.md` when slice lands.

**Effort:** Design Low–Medium; implementation **High**

---

## 9. Phase 5 — Adapter portfolio expansion (after platform + gateway MVP)

**Objective:** Close the **strategy vs tree** gap (many named providers vs **OpenAI + echo** packages today).

**Rules:**

- Each new provider ships as **`exo-adapter-<name>`** (or shares **Lane A** HTTP adapter with config-only provider entries).
- **No** new provider logic under `src/runtime/` without a **migration story** (prefer packages per `adapter-strategy.md`).

**Order (suggested):**

1. One **Lane A** universal adapter proven with **two** distinct base URLs in tests.
2. **Certification matrix** row per provider before “GA” claims.
3. Native (**Lane B**) only when universal path fails acceptance tests.

**Effort:** High per provider · **Tracker:** custom rows or epic under **COV-100-002** / product backlog

---

## 10. Risk register (condensed)

| Risk | Mitigation |
|------|------------|
| `/v1` bypasses policy | Contract tests + code review checklist; same dependency chain as `turns` |
| Contract churn breaks all adapters | Additive minors; major bump with **N-1** support window documented |
| Python mismatch hides CI failures | Phase 0 single canonical version |
| Test moves break CI | Phase 2 in small PRs; run full pytest after each batch |

---

## 11. Suggested sequencing (single team)

1. **Phase 0** (EA-001) — unblocks honest “supported stack” everywhere.
2. **Phase 1** (EA-002) — removes maintainer confusion before heavy PR volume.
3. **Phase 2.1** (FIND-001) — clears `unknown/` before large test additions for gateway/adapters.
4. **Phase 4.1** design, then **Phase 3.1–3.2** in parallel if two people; else **3.1** docs first.
5. **Phase 4.2** gateway vertical slice behind flag.
6. **Phase 3.3** certification CI hardening + **Phase 5** provider waves.

**Parallel track:** Roadmap **Stream B** (`platform_bootstrap` compat) can interleave after Phase 2.1 — reduces `app.state` drift while gateway work proceeds.

---

## 12. Crosswalk: IDs and artifacts

| This plan | Tracker / artifact |
|-----------|-------------------|
| Phase 0 | **EA-001** |
| Phase 1 | **EA-002** |
| Phase 2 | **EA-003**, **EA-004**, **FIND-001**–**FIND-006** |
| Phase 3 | **EA-006**, **EA-007** |
| Phase 4 | **EA-005** |
| Umbrella | [`post-monolith-execution-roadmap.md`](post-monolith-execution-roadmap.md) |
| Audit narrative | [`.local/workflow-artifacts/enterprise-architecture-audit/enterprise-architecture-audit.md`](../../.local/workflow-artifacts/enterprise-architecture-audit/enterprise-architecture-audit.md) |

---

## 13. Revision

| Date | Change |
|------|--------|
| 2026-03-24 | Initial plan: evidence baseline from local pytest+coverage; phases 0–5; EA/FIND crosswalk. |
| 2026-03-24 | §14: linked granular checklist `adapter-ecosystem-gateway-hygiene-todos.md`; Phase 0–1 acceptance checked after EA-001 (P0-A) + EA-002 (1b) doc alignment. |

---

## 14. Execution checklist (granular todos)

Checkbox-style tasks (Phases 0–5 + optional hygiene), crosswalk to EA/FIND IDs: [`adapter-ecosystem-gateway-hygiene-todos.md`](adapter-ecosystem-gateway-hygiene-todos.md).
