<!--
File: api.md
Path: docs/modules/api.md
Role: Module-level contract and maintenance guide for REST/SSE/WebSocket API transport.
Used By:
 - Maintainers modifying API routers, schemas, auth middleware, and bootstrap wiring
Depends On:
 - src/api/
 - tests/modules/api/
Notes:
 - API is canonical integration surface for Option C API-first operation.
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

## Operational Links

- `docs/operations/release-candidate-signoff-checklist.md`
- `docs/plans/tenant-tool-execution-architecture.md`

## Breaking-Change Policy

- Any API contract, router path, or event envelope change requires:
  - schema/test updates in `tests/modules/api/`
  - docs updates for endpoint tables and operations guidance
  - explicit compatibility note for external integrators
