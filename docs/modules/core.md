<!--
File: core.md
Path: docs/modules/core.md
Role: Module-level contract and maintenance guide for core orchestration components.
Used By:
 - docs/modules/README.md
 - Maintainers modifying orchestration/session/scheduler behavior
Depends On:
 - src/core/
 - src/integration/host_adapter.py
 - src/modules/turn_execution/service.py
 - tests/modules/core/
Notes:
 - Core must remain provider-neutral and policy-governed for side effects.
 - Workflow multi-step logic stays here; provider adapters execute turns only (see docs/runtime_contracts.md).
-->

# Core Module

## Metadata

- Status: `active`
- Owner: Savin I. Razvan
- Last validated commit: `HEAD`
- Last reviewed: `2026-05-29`

## Primary Code Paths

- `src/core/orchestrator.py` — turn loop, tool intent handling, runtime delegation
- `src/core/session_context.py` — per-session orchestrator + registry handles
- `src/core/session_store.py` — session metadata persistence seam
- `src/core/run_control_registry.py` — active run tracking for admin cancel paths
- `src/core/background_runtime.py` — deferred / background work scheduling
- `src/core/scheduler.py`, `src/core/task_graph.py`, `src/core/worker_pool.py` — workflow-style execution
- `src/core/workflow_loader.py` — workflow definition loading
- `src/core/event_router.py`, `src/core/checkpoint_store.py` — event routing and checkpoints
- `src/core/agent_scaler.py` — agent scaling hooks (orchestration-side)
- `src/integration/host_adapter.py` — thin host boundary into `Orchestrator` (API uses governed paths in `turns.py` today)
- `src/modules/turn_execution/service.py` — adapter progress semantics helper (not a full `AppModules` slice)

## Primary Tests

- `tests/modules/core/` — orchestrator, scheduler, session, shared-state backends
- **Anchors:** `test_orchestrator_turn.py`, `test_orchestrator_branches.py`

## Contract Boundaries

- Consumes **provider-neutral** `RuntimeAdapter` only (`src/runtime/runtime_adapter.py`).
- Emits deterministic execution events and run lifecycle transitions (`src/schemas/events.py`).
- Must **not** import provider SDKs or adapter package internals directly.
- State-changing tool side effects go through `DeterministicToolExecutor` + policy middleware (see [policies.md](policies.md)).
- **Do not** call `Orchestrator.run_turn` directly from customer HTTP handlers — use `src/api/routers/turns.py` so ingress, entitlements, and audit run first ([governed-execution-pipeline.md](../architecture/governed-execution-pipeline.md)).

## Operational Links

- [governed-execution-pipeline.md](../architecture/governed-execution-pipeline.md)
- [tenant-tool-execution-architecture.md](../plans/tenant-tool-execution-architecture.md)
- [runtime_contracts.md](../runtime_contracts.md) — workflow vs chat/agents ownership
- [release-candidate-signoff-checklist.md](../operations/release-candidate-signoff-checklist.md)

## Breaking-Change Policy

- Any change to run lifecycle semantics, scheduler behavior, or event envelopes requires:
  - module doc update
  - matching test updates in `tests/modules/core/`
  - architecture gate verification before merge
  - customer API / notebook docs if externally visible event shapes change
