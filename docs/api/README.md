<!--
File: README.md
Path: docs/api/README.md
Role: Index for customer-facing API integration documentation.
Used By:
 - docs/README.md
 - docs/plans/docs-inventory-master.md
Depends On:
 - docs/api/customer-api-integration-guide.md
 - docs/strategy/customer-self-serve-governance-journey.md
 - docs/architecture/governed-execution-pipeline.md
Notes:
 - Planned docs stay listed as planned until published in-tree.
-->

# API documentation

Customer integration contracts for the eXo-brain **control plane** (REST, SSE, WebSocket). Optional **customer bridge:** `POST /v1/chat/completions` when `EXO_ENABLE_OPENAI_COMPAT_GATEWAY=1`.

## Recommended reading order

| Order | Document | Audience |
|---|---|---|
| 1 | [customer-api-integration-guide.md](customer-api-integration-guide.md) | **Wire-level** reference: auth, tiers, endpoints, examples |
| 2 | [customer-self-serve-governance-journey.md](../strategy/customer-self-serve-governance-journey.md) | Product intent, scope checklist, safe iteration |
| 3 | [foundation-tier-adoption-checklist.md](../strategy/foundation-tier-adoption-checklist.md) | Foundation onboarding steps |
| 4 | [governed-execution-pipeline.md](../architecture/governed-execution-pipeline.md) | Canonical turn ordering (ingress → orchestrator → tools) |
| 5 | [adapter-installation.md](../operations/adapter-installation.md) | Published adapter wheels and `adapter_class_ref` values |

## Path convention

Tenant-scoped routers are mounted under **`/tenants`** in `src/api/app.py`. Examples in the integration guide use full paths such as `POST /tenants/{tenant_id}/sessions/{session_id}/turns`. Global routes (no tenant prefix) include `POST /providers`, `POST /admin/keys`, `GET /health`, `GET /ready`, and optional `GET /metrics`.

## Active

| Document | Status |
|---|---|
| [customer-api-integration-guide.md](customer-api-integration-guide.md) | Active — tier-aware contract reference |

## Planned in-tree

| Document | Tracked in |
|---|---|
| `governance-preview-and-testing.md` | [traceability-matrix.md](../strategy/traceability-matrix.md) — simulation/dry-run patterns, governance feedback loops |
| `docs/operations/governance-reason-code-catalog.md` | Same matrix — reason-code catalog (operations folder) |

## Implementation source of truth

- Routers: `src/api/routers/`
- OpenAPI (dev/test): set `EXO_ENABLE_OPENAPI=1` or use `EXO_ENV=development` — `/docs`, `/openapi.json`
- Regression anchors: `tests/modules/api/`
