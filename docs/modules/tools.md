<!--
File: tools.md
Path: docs/modules/tools.md
Role: Module-level contract and maintenance guide for deterministic tool execution and tool runtimes.
Used By:
 - docs/modules/README.md
 - Maintainers modifying tool registry, deterministic executor, hosted sandbox, and BYOC paths
Depends On:
 - src/tools/
 - src/modules/tool_management/service.py
 - tests/modules/tools/
Notes:
 - Tool calls are model intent; deterministic runtime performs side effects.
-->

# Tools Module

## Metadata

- Status: `active`
- Owner: Savin I. Razvan
- Last validated commit: `HEAD`
- Last reviewed: `2026-05-29`

## Primary Code Paths

- `src/tools/executor.py` — `DeterministicToolExecutor` (authoritative side effects)
- `src/tools/execution_adapter.py` — runtime-facing execution adapter seam
- `src/tools/registry.py` — tenant tool registry
- `src/tools/artifact_store.py` — uploaded package storage + signing
- `src/tools/version_projection.py` — active version projection into registry
- `src/tools/user_tools.py`, `src/tools/user_tool_contracts.py`, `src/tools/decorators.py`
- `src/tools/sandbox/` — hosted sandbox runtime (`runtime.py`, `pool.py`, `policy.py`, `process_runner.py`)
- `src/tools/byoc/` — BYOC job store, worker auth, connector runtime, integrity verifier
- `src/tools/plugins/plugin_manager.py`, `src/tools/plugins/plugin_contract.py`
- `src/modules/tool_management/service.py` — API-facing tool lifecycle seam
- `src/api/routers/tools.py` — register/upload/version governance HTTP surface

## Primary Tests

- `tests/modules/tools/` — executor, sandbox, BYOC, artifacts, version projection
- `tests/modules/api/test_slice2_tools_agents.py`, `test_tool_version_api.py` — HTTP governance paths
- **Anchors:** `test_execution_adapter.py`, `test_byoc_runtime.py`, `test_sandbox_runtime.py`

## Contract Boundaries

- **Deterministic executor** is authoritative for state-changing or high-risk tool execution.
- Tool runtime adapters (sandbox/BYOC) return structured `ToolResult` envelopes — raw exceptions must not leak to the model ([edge_02 notebook](../../notebooks/edge_02_tool_error_envelopes.ipynb)).
- Policy middleware wraps execution before/after tool calls ([policies.md](policies.md)).
- Upload paths enforce `tool_package_policy` + size/dependency gates at the API layer.
- BYOC paths use idempotency, worker tokens, and DLQ semantics documented in operations runbooks.

## Operational Links

- [governed-execution-pipeline.md](../architecture/governed-execution-pipeline.md)
- [plugin_lifecycle.md](../plugin_lifecycle.md)
- [byoc-failure-injection-playbook.md](../operations/byoc-failure-injection-playbook.md)
- [byoc-artifact-integrity-dashboard.md](../operations/byoc-artifact-integrity-dashboard.md)
- [customer-api-integration-guide.md](../api/customer-api-integration-guide.md) §6 — tool HTTP routes

## Breaking-Change Policy

- Any change to tool result envelope, cancellation semantics, or BYOC idempotency behavior requires:
  - updates in `tests/modules/tools/` and affected API tests
  - streaming compatibility checks in `tests/modules/api/test_slice3_playground.py`
  - documentation update in this file and related operations runbooks
