<!--
File: api.md
Path: docs/modules/api.md
Role: Module-level contract and maintenance guide for REST/SSE/WebSocket API transport.
Used By:
 - Maintainers modifying API routers, schemas, auth middleware, and bootstrap wiring
Depends On:
 - src/api/
 - src/modules/platform_bootstrap/service.py
 - tests/modules/api/
Notes:
 - API is canonical integration surface for Option C API-first operation.
 - Composition root: `AppModules` on `app.state.modules` (see **Composition root** below).
-->

# API Module

## Metadata

- Status: `active`
- Owner: Savin I. Razvan
- Last validated commit: `HEAD`

## Primary Code Paths

- `src/api/app.py`
- `src/api/bootstrap.py`
- `src/api/dependencies.py`
- `src/api/middleware/auth.py`
- `src/api/routers/`
- `src/api/schemas/`

## Primary Tests

- `tests/modules/api/`

## Contract Boundaries

- Routes must remain tenant-scoped where applicable.
- SSE/WS event envelopes must stay consistent with runtime event schema.
- API transport must not embed orchestration logic directly.

## Composition root (`AppModules`) — FIND-007

Option C keeps a **modular monolith** composition boundary in the API layer:

- **`create_app()`** (`src/api/app.py`) constructs the FastAPI application: middleware, routers, optional **`GET /metrics`** when `EXO_ENABLE_PROMETHEUS_METRICS` is enabled, CORS, lifespan hooks, etc.
- **`bootstrap_app()`** (`src/api/bootstrap.py`) wires persistence, registries, **`AppModules`**, and calls **`configure_opentelemetry_exporters()`** when OTLP env vars are set (`src/observability/telemetry_export.py`).
- **`AppModules`** (`src/modules/platform_bootstrap/service.py`) is the typed aggregate of domain slices: `platform_bootstrap`, `identity_access`, `tenant_governance`, `provider_management`, `agent_management`, `tool_management`, `session_runtime`, `audit_observability`. Prefer **`app.state.modules`** (and `get_app_modules()` in `src/api/dependencies.py`) for new code.
- **Compatibility:** `app.state` still exposes legacy attributes for tests and gradual migration; `_build_compat_modules_from_state` / `_sync_modules_from_state` bridge flat state ↔ `AppModules` until compat debt is retired (see enterprise audit plan Phase 4 follow-up).

Routers under `src/api/routers/` should consume dependencies / `AppModules` rather than re-implementing bootstrap wiring.

## Operational Links

- `docs/operations/release-candidate-signoff-checklist.md`
- `docs/plans/tenant-tool-execution-architecture.md`

## Breaking-Change Policy

- Any API contract, router path, or event envelope change requires:
  - schema/test updates in `tests/modules/api/`
  - docs updates for endpoint tables and operations guidance
  - explicit compatibility note for external integrators
