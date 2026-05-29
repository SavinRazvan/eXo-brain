<!--
File: README.md
Path: docs/modules/README.md
Role: Index for module-level documentation linked to code and tests.
Used By:
 - docs/README.md
 - Maintainers and contributors updating module contracts
Depends On:
 - docs/plans/docs-authority-map.md
 - docs/plans/docs-inventory-master.md
 - docs/architecture/workspace-architecture.md
Notes:
 - P0 module docs are validated by scripts/docs/check_docs_metadata.py (required section markers).
-->

# Module documentation

**Status:** active  
**Owner:** Savin I. Razvan  
**Last reviewed:** 2026-05-29

Maintainer-facing contracts for the **modular monolith** under `src/`. Customer wire contracts live in [`docs/api/`](../api/README.md); enduring layer doctrine in [`docs/architecture/`](../architecture/README.md).

## Recommended reading order

| Order | Doc | When to read |
|---|---|---|
| 1 | [workspace-architecture.md](../architecture/workspace-architecture.md) | Module boundaries, dependency direction, adapter independence |
| 2 | [governed-execution-pipeline.md](../architecture/governed-execution-pipeline.md) | Turn ordering across API → ingress → orchestrator → policy → tools |
| 3 | P0 module docs below | Before changing a specific domain |

## P0 module map

| Doc | Primary `src/` tree | `src/modules/` slice (if any) | Primary tests |
|---|---|---|---|
| [core.md](core.md) | `src/core/`, `src/integration/host_adapter.py` | `turn_execution` (thin helper only) | `tests/modules/core/` |
| [runtime.md](runtime.md) | `src/runtime/` | `provider_management`, `session_runtime` (wiring) | `tests/modules/runtime/`, `tests/packages/` |
| [tools.md](tools.md) | `src/tools/` | `tool_management` | `tests/modules/tools/` |
| [policies.md](policies.md) | `src/policies/` | `tenant_governance` (overlay inputs) | `tests/modules/policies/` |
| [tenancy.md](tenancy.md) | `src/tenancy/` | `tenant_governance` | `tests/modules/tenancy/`, `tests/modules/api/test_slice4_tenant_policy.py` |
| [api.md](api.md) | `src/api/` | `platform_bootstrap` composes all slices | `tests/modules/api/` |

## Related code (no dedicated module doc yet)

| Area | Path | Tests | Notes |
|---|---|---|---|
| Agents registry | `src/agents/` | `tests/modules/agents/` | Agent specs; API via `agents.py` router |
| Observability | `src/observability/` | `tests/modules/observability/` | Ingress budget, OTLP export, metrics |
| Persistence | `src/persistence/` | `tests/modules/persistence/` | SQLite stores, audit/event persistence |
| Identity | `src/identity/` | `tests/modules/identity_access/` | JWT/API key resolution |
| Audit trail | `src/audit/` | `tests/modules/audit/` | Chain + signed bundles |
| MCP | `src/mcp/` | `tests/modules/mcp/` | Optional tool transport adapters |

Published **provider runtime adapters:** [SavinRazvan/eXo_adapters](https://github.com/SavinRazvan/eXo_adapters) on PyPI; load via `src/runtime/adapter_factory.py` — see [`adapter-installation.md`](../operations/adapter-installation.md).

## Module doc template (required sections)

Each P0 file must include:

- **Metadata** (status, owner, last validated commit)
- **Primary Code Paths**
- **Primary Tests**
- **Contract Boundaries**
- **Breaking-Change Policy**

Optional: **Operational Links**, composition notes (see [api.md](api.md) for `AppModules`).

## Lint

```bash
python scripts/docs/check_docs_metadata.py
```

When changing routers or domain contracts, also sync [`docs/api/customer-api-integration-guide.md`](../api/customer-api-integration-guide.md) per [`documentation-maintenance-checklist.md`](../operations/documentation-maintenance-checklist.md).
