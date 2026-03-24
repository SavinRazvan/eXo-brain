<!--
File: enterprise-audit-remediation-plan.md
Path: docs/plans/enterprise-audit-remediation-plan.md
Role: Phased remediation plan for enterprise-style architecture audit findings (coverage, wiring, CI honesty, boundaries, lifecycle, docs).
Used By:
 - Maintainers executing post-audit hardening slices
 - PR scoping for audit closure
Depends On:
 - docs/plans/tenant-tool-execution-architecture.md
 - scripts/pr/prepare.py (merge gates)
 - .github/workflows/architecture-fitness.yml
Notes:
 - No big-bang redesign: incremental PRs, same modular monolith boundaries.
 - Refresh concrete coverage gaps with: python -m pytest --cov=src --cov-report=term-missing --cov-fail-under=100 -q
-->

# Enterprise audit remediation plan

## What is done vs not done (important)

**Done in code (merge when PR lands):**

- **Phase 1 — Coverage:** `pytest --cov=src --cov-fail-under=100` green (**100%** `src/**`); full suite on the order of **~1160+ passed**, **1 skipped** (soak).
- **Phase 2 — Stock factory env wiring:** `_default_settings()` in [`src/api/app.py`](../../src/api/app.py) parses `EXO_CONTROL_STATE_BACKEND`, `EXO_CONTROL_STATE_SQLITE_DB_PATH`, `EXO_SESSION_RUNTIME_IDLE_TTL_SECONDS`, `EXO_SESSION_RUNTIME_MAX_CACHED_SESSIONS`, `EXO_RUN_CONTROL_MAX_TERMINAL_RECORDS_PER_TENANT`; documented in [`README.md`](../../README.md); compose comments in [`docker-compose.yml`](../../docker-compose.yml); tests in [`tests/modules/api/test_app_factory_branches.py`](../../tests/modules/api/test_app_factory_branches.py).
- **Phase 3 — CI/deploy evidence:** [`architecture-fitness.yml`](../../.github/workflows/architecture-fitness.yml) honest job results + fail step; [`progressive-deploy.yml`](../../.github/workflows/progressive-deploy.yml) template labels; [`rollback_release.py`](../../scripts/release/rollback_release.py) `manual_automation_required`.
- **Phase 4 — Boundary guards:** [`ast_app_state_guard.py`](../../scripts/architecture/ast_app_state_guard.py) + [`validate_layers.py`](../../scripts/architecture/validate_layers.py); [`readiness.py`](../../src/api/readiness.py) in `ALLOWED_APP_STATE_FILES`; deps/startup `getattr(st, …)` pattern; [`test_validate_layers_app_state_getattr.py`](../../tests/modules/unknown/test_validate_layers_app_state_getattr.py).
- **Phase 5 — Tenant runtime lifecycle:** `RuntimeSettings.tenant_runtime_max_cached_contexts` + `EXO_TENANT_RUNTIME_MAX_CACHED_CONTEXTS` in [`src/api/app.py`](../../src/api/app.py); LRU eviction before adding a new tenant context in [`src/runtime/tenant_runtime.py`](../../src/runtime/tenant_runtime.py); `_log_adapter_start_session_done` for background `start_session` task failures; README env table; tests in [`tests/modules/runtime/test_tenant_runtime.py`](../../tests/modules/runtime/test_tenant_runtime.py) and [`test_app_factory_branches.py`](../../tests/modules/api/test_app_factory_branches.py).
- **Phase 6 — Compose / prod clarity:** prominent **not-for-prod** banner on [`docker-compose.yml`](../../docker-compose.yml); [`docker-compose.override.example.yml`](../../docker-compose.override.example.yml) + gitignored `docker-compose.override.yml`; README Docker subsection + observability pointers (Prometheus/OTLP rows + code refs).
- **Phase 7 — Docs / telemetry alignment:** [`customer-api-integration-guide.md`](../../docs/api/customer-api-integration-guide.md) §9.2 and header Notes describe **partial** OTLP + Prometheus baseline with code/test anchors; [`traceability-matrix.md`](../../docs/strategy/traceability-matrix.md) rows + gap table updated; [`docs/modules/api.md`](../../docs/modules/api.md) **AppModules** / composition-root narrative (**FIND-007**).

**Still open (after Phase 7 merge):** optional SQLite perf (Phase 8). Phases **2–5** merged via PR **#112**; Phases **6–7** on branch `fix/enterprise-phase7-telemetry-docs` until merged.

---

## Where we track everything

Use these together so work does not scatter:

| Location | Use for |
|----------|---------|
| **This file** (`docs/plans/enterprise-audit-remediation-plan.md`) | Single canonical **phase plan**, acceptance criteria, PR split A–G, tracker ID mapping |
| [`.local/index-and-planning/current/work-tracker.md`](../../.local/index-and-planning/current/work-tracker.md) | Exactly one **in_progress** slice; link to this plan when executing |
| [`.local/index-and-planning/current/plan.md`](../../.local/index-and-planning/current/plan.md) | Slice scope, rollback, acceptance (per implementation governance) |
| [`history/updates-log.md`](../../history/updates-log.md) | Substantive slice summaries after merge or milestone |
| **GitHub Issues** (optional) | One epic **Enterprise audit remediation** + children per phase or per PR A–G; IDs like `COV-100-002`, `FIND-007` if you use an external tracker |
| **PR descriptions** | Baseline metrics (coverage %, commit SHA), Phase 0 telemetry choice **A vs B** |

There is no second hidden backlog: if it is not in this plan + `work-tracker.md` (and optionally Issues), it is easy to lose.

### Plan ↔ codebase alignment (spot-check)

Re-verify **numbers** (`pytest` count, coverage %) on your branch before execution; they drift as tests are added.

**Checked against current tree (spot-check):**

- `src/api/app.py` **parses** `EXO_CONTROL_STATE_*`, session-cache, and run-control retention env vars into `RuntimeSettings` — **Phase 2 done** on branch / after merge.
- `src/api/readiness.py` uses **`state = application.state`** and direct attributes (listed in `ALLOWED_APP_STATE_FILES`). `validate_layers` rejects **`getattr(<…>.app.state, …)` / `getattr(application.state, …)`** via [`scripts/architecture/ast_app_state_guard.py`](../../scripts/architecture/ast_app_state_guard.py); deps/startup use **`st = request.app.state` / `st = app.state`** then **`getattr(st, …)`** for optional test doubles — **Phase 4 core done** after merge.
- `.github/workflows/progressive-deploy.yml`: real **Docker build + container smoke**; deploy/post-deploy steps are **labeled template placeholders** with honest `deploy.txt` keys (no fake `deploy-status: executed`).
- `.github/workflows/architecture-fitness.yml` `evidence_bundle_publish`: records **`needs.<job>.result`** per stage and **fails the job** if any required stage ≠ `success` — **Phase 3 done** after merge.
- `scripts/release/rollback_release.py`: JSON uses **`manual_automation_required`** / **`evidence_only`** instead of implying a rollback ran — **Phase 3 done** after merge.
- `src/modules/platform_bootstrap/service.py`: `_sync_modules_from_state` / `_build_compat_modules_from_state` still present — Phase 4 follow-up still applies.
- `src/api/dependencies.py`: compat path uses **`getattr(st, …)`** with **`st = request.app.state`** (allowed); not `getattr(request.app.state, …)`.
- `src/runtime/tenant_runtime.py`: optional **max cached tenant contexts** (LRU eviction) + **logged** background `start_session` failures — **Phase 5 done** after merge (`EXO_TENANT_RUNTIME_MAX_CACHED_CONTEXTS`, default `0` = unlimited).
- `packages/exo-adapter-echo/` and `tests/packages/test_echo_adapter_conformance.py` exist — “second adapter” claim in **What improved** is accurate.
- `docs/api/customer-api-integration-guide.md` §9.2 documents telemetry as **partial** with anchors to `telemetry_export.py`, `prometheus_metrics.py`, `bootstrap.py`, and tests — **Phase 7 done** after merge.
- `docker-compose.yml`: top-of-file **not-for-prod** banner + override example — **Phase 6 done** after merge.
- Identity tests live under **`tests/modules/identity_access/`** (there is no `tests/modules/identity/` tree today).

---

## Updated verdict (post–improvement audit)

**Summary:** The working tree is **materially better** than the last audit: modular monolith is real, runtime/provider boundary is stronger, code is **good enough for controlled production or pilot** with careful deployment settings. It is **still not enterprise-ready by default** for high-volume multi-worker operation. **No redesign** — remaining work is **hardening and operationalization**.

### What improved (evidence)

- `scripts/pr/check_testing_artifacts.py`, `scripts/architecture/validate_layers.py`, `scripts/architecture/scan_forbidden_imports.py`, `scripts/architecture/check_governance_consistency.py`, `scripts/packages/external_install_smoke.py` pass.
- Full suite: `pytest -q` green (e.g. **~1166 passed, 1 skipped**); residual warnings mostly test-only short-HMAC-key noise; strict **100%** `src/**` coverage gate green.
- Modular enforcement: `src/modules/contracts.py` + `validate_layers.py`; second adapter path via `packages/exo-adapter-echo` + conformance tests; `sqlite_audit.py` migrations + `asyncio.to_thread`; `app.py` / `readiness.py` / `Dockerfile` liveness-readiness-container basics.

### Findings still open (severity)

- **Resolved — coverage gate:** **100%** `src/**` with `--cov-fail-under=100` (re-run after each substantive change).
- **Resolved — stock deploy path env:** `create_app()` → `_default_settings()` now wires control state + session cache + run-control retention from env (see README operations table).
- **Resolved — synthetic / misleading evidence (honesty slice):** architecture-fitness summary lists **actual** job results and fails when any stage is not `success`; progressive-deploy artifact text distinguishes **template** vs **local image smoke**; rollback evidence uses **`manual_automation_required`** (integrators still replace with real automation).
- **Partial — boundary debt:** `getattr` on **`app.state` / `application.state` as first argument** is blocked repo-wide. **Follow-up (time-box):** `platform_bootstrap` `_sync_modules_from_state` / `_build_compat_modules_from_state` and any remaining compat shortcuts.
- **Improved — lifecycle:** Session LRU/idle + provider eviction unchanged; **tenant** contexts can be capped via `EXO_TENANT_RUNTIME_MAX_CACHED_CONTEXTS` (LRU eviction); fire-and-forget `start_session` still applies but **failures are logged** (operators still need metrics/alerts for sustained error rates at very high volume).
- **Improved — dev defaults:** `docker-compose.yml` still uses `EXO_ENV=development` by default, but ships an explicit **not-for-prod** banner, override example, and README warning so it is harder to mistake for an enterprise template.
- **Low — neutrality + docs drift:** e.g. `provider_schemas.py` default registration URLs/models; `providers.py` `recommended_runtime_mode="hybrid"` in list responses. **Telemetry docs:** customer guide + traceability matrix now label OTLP/Prometheus baseline as **partial** with file/test anchors; remaining gap is collector E2E / expanded catalog per roadmap.

### Missing evidence (explicit non-claims)

- Load/SLO profiles and real multi-worker deployment not re-verified here.
- OTLP collector integration not verified end-to-end; tests may only prove noop/minimal wiring.
- `src/persistence/adapters/sqlite.py` per-operation connections: high-QPS behavior **plausible, not proven**.

---

## Purpose

Close gaps from the **enterprise-style architecture audit**: restore blocking quality gates, align stock `create_app()` with `RuntimeSettings` consumed by `bootstrap`, make CI/deploy evidence truthful, tighten boundary guards, harden multi-tenant lifecycle, align docs with shipped telemetry (or label partial honestly).

## Guiding principles

- **No architecture redesign**: modular monolith + adapter wall; fix **defaults, wiring, tests, operational truthfulness**.
- **PR-first**: feature/fix/chore branch → gates → PR → workflow artifacts per repo rules.
- **Definition of done** (“fixed them all”):
  - `python -m pytest --cov=src --cov-report=term-missing --cov-fail-under=100 -q` **green**
  - `validate_layers`, `scan_forbidden_imports`, `check_governance_consistency`, `external_install_smoke` **green**
  - Stock `create_app()` can enable **SQLite control state** via **documented env** without custom `AppSettings` builders
  - CI evidence jobs **reflect reality** (or are explicitly labeled placeholder/demo)
  - Docs/strategy **match** telemetry endpoints and exporter baseline (or say **partial**)

## Severity map (rollup)

| Tier | Theme | Outcome |
|------|--------|---------|
| **P0** | `src/**` coverage gate | `--cov-fail-under=100` green |
| **P0/P1** | Stock factory vs settings | `_default_settings()` reads env for control state + session cache + run-control retention |
| **P1** | CI / deploy honesty | Evidence reflects upstream job outcomes; rollback/deploy boundaries real or honestly labeled |
| **P1** | Boundary guards | No `getattr(...state...)` bypass; reduce compat debt over time |
| **P1–P2** | Scale / lifecycle | Bounded tenant contexts; structured session start errors |
| **P2** | Docs / dev defaults | Traceability + integration guide match code; prod-oriented compose example |

---

## Phase 0 — Baseline + scope lock (~0.5 day)

**Goals:** Freeze what “all” means; avoid thrash.

**Tasks**

1. Export coverage miss list (re-run after branch checkout): files + line ranges.
2. Confirm target runtime: default **Docker image** + optional **multi-worker uvicorn**.
3. **Telemetry posture for this wave** — pick one and record in PR description or `plan.md`:
   - **A) Minimal but honest:** ship/tests match today; docs say **optional OTLP hook; partial baseline**
   - **B) Product slice:** heavier tests against exporter setup + update docs to **implemented baseline**

**Acceptance criteria**

- Written decision **A vs B** (one paragraph is enough).
- Baseline: branch, commit, `pytest -q` result, coverage **pass/fail** in PR or `updates-log.md`.

---

## Phase 1 — Restore 100% `src/**` coverage (P0) (~1–3 days)

**Status:** **Complete** — strict coverage gate green on mainline / feature branches that include the coverage restoration slice.

**Goals:** Unblock merge/CI ([`.github/workflows/architecture-fitness.yml`](../../.github/workflows/architecture-fitness.yml)).

### 1.1 Close misses (suggested order)

| File | Why first | What to cover |
|------|-----------|----------------|
| `src/api/readiness.py` | Often largest miss % | Memory skip, sqlite ok/fail, control/audit store types, error strings |
| `src/api/routers/prometheus_metrics.py` | Often 0% | Content-type/body when router included |
| `src/observability/telemetry_export.py` | Deep branches | Mock OTEL / env + patch exporters; keep deterministic |
| `src/identity/jwt_resolver.py` | JWKS path | Mock `PyJWKClient`; expired, bad sig, network failure → safe `None` |
| `src/runtime/tenant_runtime.py` | Eviction/LRU | `_evict_idle_sessions_only`, `_evict_lru_until_under_cap` branches |
| `src/core/run_control_registry.py` | Legacy JSON | SQLite rows with only `call_ids_json` migrate/read correctly |
| `src/persistence/adapters/sqlite_audit.py` | Shared conn | `_shared_conn` / lock paths |
| `src/api/app.py` | Factory branches | `EXO_ENABLE_PROMETHEUS_METRICS`, `EXO_CORS_ORIGINS` edges, OpenAPI toggles |

**Tasks**

1. Add/extend tests under `tests/modules/api/`, `tests/modules/observability/`, `tests/modules/identity_access/` (canonical layout today; `src/identity/` maps here for JWT/resolver coverage).
2. Re-run until `pytest --cov=src --cov-fail-under=100 -q` is green.
3. Regenerate coverage index if your process requires it after coverage work.

**Acceptance criteria**

- 100% `src/**` locally and in CI.

---

## Phase 2 — Stock app factory exposes scale knobs (P0) (~1–2 days)

**Status:** **Complete** — env parsing in `src/api/app.py`, README + `docker-compose.yml` guidance, black-box tests via `create_app()`.

**Goals:** `uvicorn src.api.app:create_app` can run **multi-process-safe** control plane without a custom settings builder.

**Tasks**

1. Parse in `src/api/app.py` `_default_settings()` (document in `README.md`):
   - `EXO_CONTROL_STATE_BACKEND` → `memory|sqlite`
   - `EXO_CONTROL_STATE_SQLITE_DB_PATH`
   - `EXO_SESSION_RUNTIME_IDLE_TTL_SECONDS`
   - `EXO_SESSION_RUNTIME_MAX_CACHED_SESSIONS`
   - `EXO_RUN_CONTROL_MAX_TERMINAL_RECORDS_PER_TENANT` (or standardized equivalent)
2. **Black-box tests:** `TestClient(create_app())` + `monkeypatch.setenv` — `SQLiteRunControlRegistry` / `SQLiteTenantRateLimiter` when configured (mirror spirit of [`tests/modules/api/test_bootstrap_control_sqlite.py`](../../tests/modules/api/test_bootstrap_control_sqlite.py) through **public** factory).
3. **Prod-oriented example:** commented block in `docker-compose.yml` **or** `docker-compose.prod.example.yml` with non-dev `EXO_ENV`, explicit `EXO_CORS_ORIGINS`, sqlite control backend.

**Acceptance criteria**

- Shared SQLite control state reachable from default container path via env only.

---

## Phase 3 — CI / deploy evidence honesty (P1) (~0.5–1.5 days)

**Status:** **Complete** on branch `fix/ci-evidence-honesty` — architecture summary from `needs.*.result` + fail step; progressive-deploy notes and honest deploy artifact keys; rollback script JSON/text semantics.

**Tasks**

1. [`architecture-fitness.yml`](../../.github/workflows/architecture-fitness.yml) `evidence_bundle_publish`: gate on `needs.*.result == success` **or** write `skipped/failed` explicitly — never unconditional `completed` for all lines.
2. [`progressive-deploy.yml`](../../.github/workflows/progressive-deploy.yml): real command boundaries (helm/kubectl/terraform) **or** workflow clearly labeled **demo / template only**.
3. [`scripts/release/rollback_release.py`](../../scripts/release/rollback_release.py): evolve hook **or** rename fields to `manual_required` / similar so JSON is honest.

**Acceptance criteria**

- Failed upstream jobs cannot produce a green-washing evidence bundle without explicit language.

---

## Phase 4 — Boundary guard completeness (P1) (~0.5–1 day)

**Status:** **Complete** on branch `fix/boundary-guard-readiness` — `ast_app_state_guard.py`, `readiness.py` + allowlist, deps/startup `st` binding pattern, unit tests.

**Tasks**

1. Extend [`scripts/architecture/validate_layers.py`](../../scripts/architecture/validate_layers.py) to flag `getattr(..., "state", ...)` / `getattr(application.state, ...)` (pragmatic AST walk + allowlist if needed).
2. Refactor [`src/api/readiness.py`](../../src/api/readiness.py) to approved patterns.
3. **Follow-up (time-box):** trim `_sync_modules_from_state` / `_build_compat_modules_from_state` in [`platform_bootstrap/service.py`](../../src/modules/platform_bootstrap/service.py) when safe (`dependencies.py` compat path already uses `st = request.app.state` + `getattr(st, …)`).

**Acceptance criteria**

- `validate_layers.py` passes; readiness semantics unchanged for `/ready` consumers.

---

## Phase 5 — Runtime lifecycle hardening (P1–P2) (~2–4 days)

**Status:** Implemented on `fix/tenant-runtime-lifecycle` — max tenant contexts + LRU eviction; `start_session` still scheduled asynchronously but failures are **logged** (`_log_adapter_start_session_done`). Further hardening (await init, surface error on first `run_turn`) remains optional.

**Tasks (done for this slice)**

1. **Tenant `_contexts` cap:** `tenant_runtime_max_cached_contexts` / `EXO_TENANT_RUNTIME_MAX_CACHED_CONTEXTS` (`0` = unlimited); LRU eviction via `_tenant_last_touch` before inserting a new tenant.
2. **Session start:** keep `create_task` under running loop; add done-callback logging for exceptions (no silent asyncio failures).
3. **Tests:** tenant LRU eviction; cancelled-task noop; failed `start_session` log path; `_default_settings` env wiring.

**Acceptance criteria**

- Bounded tenant context growth when env cap is set; no silent background failures for `start_session` (logged at ERROR). Optional follow-up: stricter client-visible init contract.

---

## Phase 6 — Security / edge defaults (P1) (~0.5 day)

**Status:** Implemented on `fix/enterprise-phase6-compose-readme` — banner + `docker-compose.override.example.yml` + `.gitignore` for `docker-compose.override.yml`; README Docker + observability pointers.

**Tasks (done for this slice)**

1. `docker-compose.yml`: prominent warnings; optional merge via `docker-compose.override.yml` (example committed as `docker-compose.override.example.yml`).
2. `README.md`: Docker safety paragraph; operations table already includes control state, session/tenant cache, Prometheus, OTLP — added code pointers in the table intro.

**Acceptance criteria**

- Reviewers cannot mistake default compose for enterprise prod template.

---

## Phase 7 — Docs + traceability alignment (P1) (~1 day)

**Status:** Implemented on `fix/enterprise-phase7-telemetry-docs` — customer guide §9.2 + Notes; traceability matrix runtime/telemetry rows + OTel/Prometheus gap row; `docs/modules/api.md` composition / `AppModules` section.

**Tasks (done for this slice)**

1. [`docs/api/customer-api-integration-guide.md`](../../docs/api/customer-api-integration-guide.md) and [`docs/strategy/traceability-matrix.md`](../../docs/strategy/traceability-matrix.md): **partial** baseline for OTLP + Prometheus with code/test anchors; roadmap items explicit.
2. [`docs/modules/api.md`](../../docs/modules/api.md): `AppModules` / composition-root narrative (**FIND-007**).

**Low (optional same PR or later):** provider schema defaults / list `recommended_runtime_mode` copy — neutrality polish, not coverage-blocking.

**Acceptance criteria**

- No “planned” for shipped code unless labeled **partial** with file/test anchors.

---

## Phase 8 — Optional performance slice (P2)

**Tasks**

1. Evaluate unifying file-backed SQLite in [`sqlite.py`](../../src/persistence/adapters/sqlite.py) vs risk of behavior change.
2. Short perf note or micro-benchmark record if gates exist.

**Acceptance criteria**

- Decision recorded (unify vs defer).

---

## Execution checklist (every PR)

1. `python scripts/pr/check_testing_artifacts.py`
2. `python -m pytest --cov=src --cov-report=term-missing --cov-fail-under=100 -q` (when `src/**` touched)
3. `python scripts/architecture/validate_layers.py`
4. `python scripts/architecture/scan_forbidden_imports.py`
5. `python scripts/architecture/check_governance_consistency.py` (governance/workflows/docs indexes)
6. `python scripts/packages/external_install_smoke.py` (packages/adapters)
7. Update `work-tracker.md` / `test-index.md` / `test-plan.md` as needed; `updates-log.md` for substantive slices

---

## Suggested PR breakdown

| PR | Scope |
|----|--------|
| **A** | Phase 1 only — 100% coverage |
| **B** | Phase 2 — env + black-box tests + prod compose example |
| **C** | Phase 3 — CI + deploy + rollback honesty |
| **D** | Phase 4 — validator + readiness (+ compat time-box if included) |
| **E** | Phase 5 — lifecycle |
| **F** | Phases 6–7 — compose + docs |
| **G** (optional) | Phase 8 — SQLite perf |

---

## Tracker mapping

| ID | Maps to |
|----|---------|
| **COV-100-002** | Phase 1 (+ coverage index regeneration if required by process) |
| **FIND-007** | Phase 7 — `docs/modules/api.md` |
| **FIND-001 / FIND-004 / FIND-005** | Easier after Phases 1–2 (test re-homing / compat) |

For GitHub: one **epic** + child issues per phase **or** one issue per PR **A–G**.

---

## Revision

| Date | Change |
|------|--------|
| 2026-03-22 | Initial plan from audit synthesis. |
| 2026-03-24 | Added done-vs-not-done, tracking table, updated verdict (99.19% gate, improved areas), Phase 0 A/B telemetry, ordered Phase 1 table, progressive-deploy nuance, compat debt, missing evidence, external_install_smoke in checklist, tracker IDs. |
| 2026-03-24 | Plan↔codebase spot-check: alignment subsection, Phase 1 test path fixed to `identity_access` only, validator/readiness bypass clarified. |
| 2026-03-24 | Phase 1–2 marked complete: 100% coverage baseline, `EXO_CONTROL_STATE_*` and related env wiring in `app.py`, README/compose, tests. |
| 2026-03-24 | Phase 3: architecture-fitness evidence from job results + fail on non-success; progressive-deploy honest placeholder labels; rollback `manual_automation_required` / `evidence_only`. |
| 2026-03-24 | Phase 4: `ast_app_state_guard` + getattr-on-app.state ban; readiness direct `state`; deps/startup `getattr(st,…)`; tests load guard module only for coverage safety. |
| 2026-03-24 | Phase 5: tenant runtime LRU cap + `start_session` error logging; env `EXO_TENANT_RUNTIME_MAX_CACHED_CONTEXTS`. |
| 2026-03-24 | Phase 6: compose not-for-prod banner, `docker-compose.override.example.yml`, README Docker safety. |
| 2026-03-24 | Phase 7: customer guide + traceability matrix **partial** telemetry; `docs/modules/api.md` `AppModules` composition narrative. |
