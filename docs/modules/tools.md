<!--
File: tools.md
Path: docs/modules/tools.md
Role: Module-level contract and maintenance guide for deterministic tool execution and tool runtimes.
Used By:
 - Maintainers modifying tool registry, deterministic executor, hosted sandbox, and BYOC paths
Depends On:
 - src/tools/
 - tests/modules/tools/
Notes:
 - Tool calls are intent from model; deterministic runtime performs side effects.
-->

# Tools Module

## Metadata

- Status: `active`
- Owner: Savin I. Razvan
- Last validated commit: `HEAD`

## Primary Code Paths

- `src/tools/executor.py`
- `src/tools/registry.py`
- `src/tools/execution_adapter.py`
- `src/tools/sandbox/`
- `src/tools/byoc/`
- `src/tools/plugins/plugin_manager.py`

## Primary Tests

- `tests/modules/tools/`

## Contract Boundaries

- Deterministic executor is authoritative for state-changing or high-risk tool execution.
- Tool runtime adapters (sandbox/BYOC) must return structured result envelopes.
- Policy middleware wraps execution before and after tool calls.

## Operational Links

- `docs/plugin_lifecycle.md`
- `docs/operations/byoc-failure-injection-playbook.md`
- `docs/operations/byoc-artifact-integrity-dashboard.md`

## Breaking-Change Policy

- Any change to tool result envelope, cancellation semantics, or BYOC idempotency behavior requires:
  - update in `tests/modules/tools/`
  - streaming compatibility checks in API tests
  - documentation update in this file and related operations runbooks
