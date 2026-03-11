<!--
File: core.md
Path: docs/modules/core.md
Role: Module-level contract and maintenance guide for core orchestration components.
Used By:
 - Maintainers modifying orchestration/session/scheduler behavior
Depends On:
 - src/core/
 - tests/modules/core/
Notes:
 - Core must remain provider-neutral and policy-governed for side effects.
-->

# Core Module

## Metadata

- Status: `active`
- Owner: Savin I. Razvan
- Last validated commit: `HEAD`

## Primary Code Paths

- `src/core/orchestrator.py`
- `src/core/background_runtime.py`
- `src/core/scheduler.py`
- `src/core/task_graph.py`
- `src/core/worker_pool.py`
- `src/core/run_control_registry.py`
- `src/core/session_context.py`
- `src/core/session_store.py`

## Primary Tests

- `tests/modules/core/`

## Contract Boundaries

- Accepts provider-neutral runtime interface only (`RuntimeAdapter` contract).
- Emits deterministic execution events and run lifecycle transitions.
- Must not import provider SDKs directly.

## Operational Links

- `docs/operations/release-candidate-signoff-checklist.md`
- `docs/plans/tenant-tool-execution-architecture.md`

## Breaking-Change Policy

- Any change to run lifecycle semantics, scheduler behavior, or event envelopes requires:
  - module doc update
  - matching test updates in `tests/modules/core/`
  - architecture gate verification before merge
