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

**Still open:** honest CI/deploy evidence (Phase 3), `validate_layers` + readiness bypass (Phase 4), tenant-context / session-start hardening (Phase 5), prod compose warnings depth (Phase 6), docs/telemetry alignment (Phase 7), optional SQLite perf (Phase 8).

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
- `src/api/readiness.py` still uses `getattr(application.state, ...)` for `session_store`, `run_control_registry`, `audit_store`. `readiness.py` is in `_EXTRA_BOUNDARY_FILES` in `validate_layers.py` for **module import** rules, but it is **not** in `ALLOWED_APP_STATE_FILES`, and **`getattr(..., "state", ...)` is not the same as `app.state` in the AST check** — so the guard is bypassed; Phase 4 still applies.
- `.github/workflows/progressive-deploy.yml`: real **Docker build + container smoke** (`/health`, `/ready`); **Deploy release** and **Health check** steps are still explicitly **placeholder**.
- `.github/workflows/architecture-fitness.yml` `evidence_bundle_publish`: still `if: always()` with static `completed` lines — Phase 3 still applies.
- `scripts/release/rollback_release.py` still documents stub / `stub_executed`-style evidence — Phase 3 still applies.
- `src/modules/platform_bootstrap/service.py`: `_sync_modules_from_state` / `_build_compat_modules_from_state` still present — Phase 4 follow-up still applies.
- `src/api/dependencies.py`: `request.app.state.*` and `getattr(request.app.state, ...)` fallbacks still present — Phase 4 still applies.
- `src/runtime/tenant_runtime.py`: `self._contexts` dict and `loop.create_task(...)` for async work still present — Phase 5 still applies.
- `packages/exo-adapter-echo/` and `tests/packages/test_echo_adapter_conformance.py` exist — “second adapter” claim in **What improved** is accurate.
- `docs/api/customer-api-integration-guide.md` still states standard telemetry export is **planned** (file header Notes and **§9.2**) while `telemetry_export.py` / `prometheus_metrics.py` exist — Phase 7 still applies.
- Identity tests live under **`tests/modules/identity_access/`** (there is no `tests/modules/identity/` tree today).

---

## Updated verdict (post–improvement audit)

**Summary:** The working tree is **materially better** than the last audit: modular monolith is real, runtime/provider boundary is stronger, code is **good enough for controlled production or pilot** with careful deployment settings. It is **still not enterprise-ready by default** for high-volume multi-worker operation. **No redesign** — remaining work is **hardening and operationalization**.

### What improved (evidence)

- `scripts/pr/check_testing_artifacts.py`, `scripts/architecture/validate_layers.py`, `scripts/architecture/scan_forbidden_imports.py`, `scripts/architecture/check_governance_consistency.py`, `scripts/packages/external_install_smoke.py` pass.
- Full suite: `pytest -q` green (e.g. **~1161 passed, 1 skipped**); residual warnings mostly test-only short-HMAC-key noise; strict **100%** `src/**` coverage gate green.
- Modular enforcement: `src/modules/contracts.py` + `validate_layers.py`; second adapter path via `packages/exo-adapter-echo` + conformance tests; `sqlite_audit.py` migrations + `asyncio.to_thread`; `app.py` / `readiness.py` / `Dockerfile` liveness-readiness-container basics.

### Findings still open (severity)

- **Resolved — coverage gate:** **100%** `src/**` with `--cov-fail-under=100` (re-run after each substantive change).
- **Resolved — stock deploy path env:** `create_app()` → `_default_settings()` now wires control state + session cache + run-control retention from env (see README operations table).
- **Medium — synthetic evidence:** `progressive-deploy.yml` may build image and probe `/health` / `/ready`, but deploy/post-deploy steps can remain placeholders; `rollback_release.py` still `rollback_status: stub_executed`; `architecture-fitness.yml` `evidence_bundle_publish` can still write unconditional `completed` lines.
- **Medium — boundary debt:** `src/modules/platform_bootstrap/service.py` keeps `_sync_modules_from_state` / `_build_compat_modules_from_state`; `src/api/dependencies.py` has raw `request.app.state` fallbacks; `readiness.py` uses `getattr(application.state, ...)`, bypassing `validate_layers.py` rules for explicit `app.state` access.
- **Medium — lifecycle:** `tenant_runtime.py` has session LRU/idle controls and provider eviction, but tenant `_contexts` remain unbounded and `start_session` can be fire-and-forget — OK for controlled rollout, weak story for very high tenant/tool volume.
- **Medium — dev defaults:** `docker-compose.yml` uses `EXO_ENV=development`; wildcard CORS in dev/test when `EXO_CORS_ORIGINS` unset — fine locally, risky as a prod template.
- **Low — neutrality + docs drift:** e.g. `provider_schemas.py` default registration URLs/models; `providers.py` `recommended_runtime_mode="hybrid"` in list responses; telemetry code exists but customer guide / traceability matrix still describe interoperability as “planned” in places.

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

**Tasks**

1. [`architecture-fitness.yml`](../../.github/workflows/architecture-fitness.yml) `evidence_bundle_publish`: gate on `needs.*.result == success` **or** write `skipped/failed` explicitly — never unconditional `completed` for all lines.
2. [`progressive-deploy.yml`](../../.github/workflows/progressive-deploy.yml): real command boundaries (helm/kubectl/terraform) **or** workflow clearly labeled **demo / template only**.
3. [`scripts/release/rollback_release.py`](../../scripts/release/rollback_release.py): evolve hook **or** rename fields to `manual_required` / similar so JSON is honest.

**Acceptance criteria**

- Failed upstream jobs cannot produce a green-washing evidence bundle without explicit language.

---

## Phase 4 — Boundary guard completeness (P1) (~0.5–1 day)

**Tasks**

1. Extend [`scripts/architecture/validate_layers.py`](../../scripts/architecture/validate_layers.py) to flag `getattr(..., "state", ...)` / `getattr(application.state, ...)` (pragmatic AST walk + allowlist if needed).
2. Refactor [`src/api/readiness.py`](../../src/api/readiness.py) to approved patterns.
3. **Follow-up (time-box):** trim `_sync_modules_from_state` / `_build_compat_modules_from_state` in [`platform_bootstrap/service.py`](../../src/modules/platform_bootstrap/service.py) and `request.app.state` fallbacks in [`dependencies.py`](../../src/api/dependencies.py) when safe.

**Acceptance criteria**

- `validate_layers.py` passes; readiness semantics unchanged for `/ready` consumers.

---

## Phase 5 — Runtime lifecycle hardening (P1–P2) (~2–4 days)

**Tasks**

1. **Tenant `_contexts` strategy** (choose one, document): LRU+TTL, explicit destroy + sweeper, or max tenants per process + metrics.
2. **Session start:** replace fire-and-forget `create_task` with `await` where safe **or** structured background work with **deterministic client error** on first `run_turn` if init failed.
3. Tests: idle eviction, tenant eviction safety, failed `start_session` behavior.

**Acceptance criteria**

- No silent “session will appear later” failures on happy path; bounded growth under documented defaults for bounded workload.

---

## Phase 6 — Security / edge defaults (P1) (~0.5 day)

**Tasks**

1. `docker-compose.yml`: prominent warnings; optional `compose.override.yml` for dev-only wildcard CORS.
2. `README.md` operations env table (control state + session cache + Prometheus/OTLP pointers).

**Acceptance criteria**

- Reviewers cannot mistake default compose for enterprise prod template.

---

## Phase 7 — Docs + traceability alignment (P1) (~1 day)

**Tasks**

1. [`docs/api/customer-api-integration-guide.md`](../../docs/api/customer-api-integration-guide.md) and [`docs/strategy/traceability-matrix.md`](../../docs/strategy/traceability-matrix.md): match Phase 0 **A vs B** (partial vs productized).
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
