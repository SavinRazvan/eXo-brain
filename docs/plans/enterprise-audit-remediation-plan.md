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

## Purpose

Close gaps found in a full **enterprise-style architecture audit**: restore blocking quality gates, align stock `create_app()` configuration with `RuntimeSettings` fields already consumed by `bootstrap`, make CI/deploy evidence truthful, tighten boundary guards, harden multi-tenant lifecycle edges, and align customer/strategy docs with implemented telemetry.

## Guiding principles

- **PR-first**: feature/fix/chore branch → tests → architecture gates → PR → merge workflow artifacts per repo rules.
- **No provider branching in core**; keep SDKs behind adapters.
- **Definition of done** is explicit per phase (commands + observable outcomes).

## Severity map (rollup)

| Tier | Theme | Outcome |
|------|--------|---------|
| **P0** | `src/**` coverage gate | `pytest` with `--cov-fail-under=100` green in CI and locally |
| **P0/P1** | Stock factory vs settings | `create_app()` / `_default_settings()` reads env for control-plane + session cache knobs already on `RuntimeSettings` |
| **P1** | CI / deploy honesty | Evidence bundles reflect real job outcomes; rollback/deploy docs match code |
| **P1** | Boundary guards | Layer/fitness scripts cannot be trivially bypassed (e.g. dynamic `getattr` on `app.state`) |
| **P1–P2** | Scale / lifecycle | Bounded tenant caches, structured background work, documented limits |
| **P2** | Docs / dev defaults | Traceability + integration guide match OTLP/Prometheus reality; dev CORS/SQLite warnings |

---

## Phase 0 — Baseline and scope lock

**Goals:** Freeze what “done” means for this effort; capture current numbers.

**Tasks**

1. Record current branch, `python -m pytest -q` result, and strict coverage command outcome.
2. Confirm telemetry posture: OTLP + optional Prometheus router (`EXO_ENABLE_PROMETHEUS_METRICS`) vs docs that still say “planned”.
3. Skim `docs/plans/tenant-tool-execution-architecture.md` and `.local/index-and-planning/current/plan.md` for overlapping scope; link this plan from `work-tracker.md` when execution starts.

**Acceptance criteria**

- Written baseline (date, commit, pass/fail on coverage gate) stored in PR description or `updates-log.md` entry.

---

## Phase 1 — Restore 100% `src/**` coverage (P0)

**Goals:** Satisfy `.github/workflows/architecture-fitness.yml` (`--cov-fail-under=100`).

**Primary targets** (re-verify with `coverage report`; names reflect typical gaps):

| Area | File(s) | Notes |
|------|---------|--------|
| Readiness | `src/api/readiness.py` | SQLite quick-check branches, non-SQLite stores |
| Metrics router | `src/api.routers/prometheus_metrics.py` | Include router only when flag on; hit endpoints in tests |
| App factory | `src/api/app.py` | CORS branches, OpenAPI toggles, Prometheus conditional include |
| Telemetry | `src/observability/telemetry_export.py` | OTLP wiring / no-op paths |
| Identity | `src/identity/jwt_resolver.py` | JWKS vs HS paths, failure modes |
| Tenant runtime | `src/runtime/tenant_runtime.py` | Idle TTL / eviction branches |
| Run control | `src/core/run_control_registry.py` | Legacy JSON / SQLite branches |
| Audit adapter | `src/persistence/adapters/sqlite_audit.py` | Shared-connection vs dedicated connection paths |

**Tasks**

1. Add **module-aligned** tests under `tests/modules/<module>/` (black-box HTTP tests where appropriate; unit tests for pure branches).
2. Prefer deterministic temp dirs / `:memory:` where SQLite is involved; respect `.local` rules for `.exo_data/`.
3. Re-run full suite with coverage until **100%** on `src/**`.

**Acceptance criteria**

- `python -m pytest --cov=src --cov-report=term-missing --cov-fail-under=100 -q` passes locally and in CI.

---

## Phase 2 — Wire `RuntimeSettings` scale/control knobs in `_default_settings()` (P0/P1)

**Problem:** `RuntimeSettings` includes fields used by `src/api/bootstrap.py` and `src/runtime/tenant_runtime.py`, but `src/api/app.py` → `_default_settings()` currently builds `RuntimeSettings` with many explicit env-driven BYOC fields while leaving **at least** these to dataclass defaults only:

- `control_state_backend`, `control_state_sqlite_db_path`
- `session_runtime_idle_ttl_seconds`, `session_runtime_max_cached_sessions`
- `run_control_max_terminal_records_per_tenant`

**Proposed env vars** (add parsing in `_default_settings()`, document in README / operations):

| Setting field | Suggested env |
|---------------|----------------|
| `control_state_backend` | `EXO_CONTROL_STATE_BACKEND` |
| `control_state_sqlite_db_path` | `EXO_CONTROL_STATE_SQLITE_DB_PATH` |
| `session_runtime_idle_ttl_seconds` | `EXO_SESSION_RUNTIME_IDLE_TTL_SECONDS` |
| `session_runtime_max_cached_sessions` | `EXO_SESSION_RUNTIME_MAX_CACHED_SESSIONS` |
| `run_control_max_terminal_records_per_tenant` | `EXO_RUN_CONTROL_MAX_TERMINAL_RECORDS_PER_TENANT` |

**Tasks**

1. Parse and validate integers (non-negative where required); keep defaults identical to current `RuntimeSettings` defaults for backward compatibility.
2. Add **black-box** tests: `create_app()` + bootstrap path respects env (extend patterns in `tests/modules/api/test_bootstrap_control_sqlite.py`).
3. Update `docker-compose.yml` comments / examples for production-oriented values (without breaking dev ergonomics).

**Acceptance criteria**

- Setting each env var changes observable behavior (e.g. SQLite control registry file path, eviction behavior) with tests proving wiring.
- Defaults unchanged when env unset.

---

## Phase 3 — CI and deploy evidence honesty (P1)

**Goals:** Workflows and scripts must not claim success when upstream jobs failed or when behavior is stubbed.

**Known issues**

1. **`architecture-fitness.yml` — `evidence_bundle_publish`**: uses `if: always()` and writes static `completed` lines for all stages, regardless of actual job results.

**Tasks**

1. Gate evidence generation on **successful** completion of required upstream jobs (or embed actual job conclusions from `needs` / workflow API if you need a single aggregate artifact).
2. **`progressive-deploy.yml`**: replace placeholders with documented interfaces, or mark clearly as **non-production** / template with explicit TODOs in workflow comments.
3. **`scripts/release/rollback_release.py`**: keep stub only if labeled; otherwise implement minimal real hook (e.g. readiness GET already partially supported) and document integrator extension point.

**Acceptance criteria**

- A failing `automated_test_suite` does not produce an “all green” architecture evidence artifact unless the artifact explicitly lists failures.
- Rollback script output JSON fields match real behavior (`stub_executed` vs executed automation).

---

## Phase 4 — Boundary guard completeness (P1)

**Goals:** `scripts/architecture/validate_layers.py` (and related guards) catch patterns that bypass static checks.

**Known issue:** `src/api/readiness.py` uses `getattr(application.state, ...)` instead of typed / enumerated `app.state` access, which can evade AST-based guards.

**Tasks**

1. Extend the validator to flag **forbidden** `getattr(application.state, ...)` (or equivalent) patterns, with allowlist if needed.
2. Refactor readiness to use an **approved** access pattern: e.g. narrow protocol on `app.state`, explicit attributes set in bootstrap, or helper on the app instance.

**Acceptance criteria**

- Validator fails on reintroduced bypass patterns.
- Readiness behavior unchanged from an API consumer perspective (`/ready` schema and semantics).

---

## Phase 5 — Runtime lifecycle hardening (P1–P2)

**Goals:** Predictable memory and task behavior under multi-tenant load.

**Themes**

- **Bounded caches:** `_contexts` / session caches — LRU + TTL, max tenants per process, or explicit destroy hooks (document chosen strategy in `docs/architecture/workspace-architecture.md` or execution plan).
- **Background tasks:** Replace fire-and-forget `asyncio.create_task` where errors must surface (session assembly); use structured task ownership and logging with correlation IDs.

**Tasks**

1. Document limits and operational tuning in docs + env table (ties to Phase 2).
2. Implement eviction / cap with tests (including “idle eviction fires” and “session start failure observable”).
3. Ensure observability: log at warning/error with tenant/session correlation when background work fails.

**Acceptance criteria**

- Tests cover eviction and failure paths; no unbounded growth in documented default configuration for a bounded tenant/session workload scenario.

---

## Phase 6 — Security and dev defaults (P1/P2)

**Goals:** Reduce foot-guns in default developer compose.

**Tasks**

1. `docker-compose.yml`: comment that `EXO_ENV=development` and default wildcard CORS (via empty `EXO_CORS_ORIGINS` in dev) are **not** production patterns.
2. `README.md` (or `docs/operations/*`): short **operations env** table including control state, session cache, Prometheus, OTLP endpoints.

**Acceptance criteria**

- New operators see explicit warnings at copy-paste boundaries (compose + README).

---

## Phase 7 — Docs and traceability alignment (P2)

**Goals:** Strategy and customer docs match code.

**Tasks**

1. Update `docs/api/customer-api-integration-guide.md` — telemetry: OTLP export, metrics endpoint flag, correlation ID expectations.
2. Update `docs/strategy/traceability-matrix.md` — mark telemetry items as implemented vs planned where applicable.
3. Update `docs/modules/api.md` — `AppModules` / composition-root narrative vs `app.state` (post Phase 4 refactor).

**Acceptance criteria**

- No doc claims “telemetry planned” where the stack already exports or exposes metrics.

---

## Phase 8 — Optional: SQLite store unification / perf note (P2)

**Goals:** Reduce duplicate connection patterns if justified by profiling.

**Tasks**

1. Compare `src/persistence/adapters/sqlite.py` vs `sqlite_audit.py` / control registry usage.
2. If unification is deferred, add a short perf note in `docs/plans/option-c-performance-gates.md` or execution architecture doc.

**Acceptance criteria**

- Decision recorded (unify vs defer) with rationale.

---

## Execution checklist (every PR)

Per `scripts/pr/prepare.py` / repo rules:

1. `python scripts/pr/check_testing_artifacts.py`
2. `python -m pytest -q` (and coverage gate when touching `src/**`)
3. `python scripts/architecture/validate_layers.py`
4. `python scripts/architecture/scan_forbidden_imports.py`
5. When changing governance/workflows/policy docs: `python scripts/architecture/check_governance_consistency.py`
6. Update `.local/index-and-planning/current/work-tracker.md`, `test-index.md` / `test-plan.md` when risk or tests change; `history/updates-log.md` for substantive slices.

---

## Suggested PR breakdown

| PR | Scope |
|----|--------|
| **A** | Phase 1 only — 100% coverage |
| **B** | Phase 2 — env wiring + tests + compose comments |
| **C** | Phase 3 — workflow / rollback honesty |
| **D** | Phase 4 — validator + readiness refactor |
| **E** | Phase 5 — lifecycle + background task hardening |
| **F** | Phases 6–7 — docs + dev warnings |
| **G** (optional) | Phase 8 — SQLite / perf follow-up |

Phases 6–7 can ship together if small.

---

## Tracker mapping (optional)

When filing issues, one epic **“Enterprise audit remediation”** with child tickets per phase above keeps traceability. Alternatively, map **one ticket per PR (A–G)** for linear execution.

---

## Revision

| Date | Change |
|------|--------|
| 2026-03-22 | Initial plan authored from enterprise architecture audit synthesis. |
