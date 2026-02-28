# Bootstrap Checklist (Day 0 to First Vertical Slice)

## Goal
Provide a concrete startup checklist for creating the new repository and reaching a first working vertical slice fast, while preserving modular, dynamic, scalable architecture constraints.

## Inputs
- `02-target-architecture.md`
- `08-module-requirements-matrix.md`
- `10-provider-capability-matrix.md`
- `11-port-matrix.md`

## Day 0: Repository Initialization
- [ ] Create new repository with Python project scaffolding (`src/`, `tests/`, `pyproject.toml`, `README.md`).
- [x] Add `.cursor/` portable pack into new repo root.
- [ ] Create package structure:
  - [x] `src/integration`
  - [x] `src/core`
  - [x] `src/runtime`
  - [ ] `src/agents`
  - [x] `src/tools`
  - [x] `src/mcp`
  - [x] `src/persistence`
  - [x] `src/policies`
  - [x] `src/schemas`
  - [x] `src/observability`
  - [x] `src/config`
- [ ] Create test structure:
  - [x] `tests/integration`
  - [x] `tests/regression`
  - [x] `tests/performance`

## Day 1: Contracts First
- [x] Define `RuntimeAdapter` contract in `src/runtime/runtime_adapter.py`.
- [x] Define `ToolRuntime` contract in `src/tools/executor.py`.
- [x] Define policy contract in `src/policies/middleware.py`.
- [x] Define persistence contracts in `src/persistence/contracts.py`.
- [x] Define typed event/output/tool schemas in `src/schemas/*`.
- [x] Add provider capability schema in `src/runtime/capability_map.py`.

## Day 2: Provider and Mode Selection
- [x] Implement `src/runtime/mode_selector.py` with policy-aware routing:
  - [x] `provider_native`
  - [x] `deterministic`
  - [ ] fallback behavior
- [ ] Add initial adapters:
  - [x] `openai_agents_runtime.py`
  - [x] `openai_compatible_runtime.py`
  - [x] `custom_runtime.py`
- [x] Add provider registry in `src/config/provider_registry.py`.
- [x] Implement settings schema + startup validation in `src/config/settings.py` and `src/config/provider_registry.py` (see `34-provider-registry-and-settings-schema.md`).

## Day 3: Deterministic Tool Runtime
- [x] Implement descriptor-based registry in `src/tools/registry.py`.
- [x] Implement deterministic tool executor in `src/tools/executor.py`.
- [x] Add plugin lifecycle API:
  - [x] `load_plugin`
  - [x] `unload_plugin`
  - [x] `reload_plugin`
  - [x] `validate_compatibility`
- [x] Add standardized tool output envelope in `src/schemas/tool_io.py`.

## Day 4: Policy + Decorators + Safety
- [x] Implement pre/post policy checks in `src/policies/middleware.py`.
- [x] Add `src/tools/decorators.py` with hooks for:
  - [x] validation
  - [x] authz
  - [x] retries
  - [x] audit logging
  - [x] redaction
- [x] Enforce deterministic execution for risky/state-changing calls.

## Day 5: Core Orchestration + Event Routing
- [x] Implement `src/core/orchestrator.py` with clear boundaries.
- [x] Implement `src/core/event_router.py` (event map pattern).
- [x] Implement session and correlation context in `src/core/session_context.py`.
- [x] Ensure integration boundary in `src/integration/host_adapter.py` remains transport-agnostic.
- [x] Implement persistence adapters in `src/persistence/adapters/` (`postgres`, `sqlite`) with parity tests.

## Day 6: Background Runtime Foundation
- [x] Define `TaskGraph` model and scheduler contract.
- [x] Implement initial bounded worker pool.
- [x] Implement checkpoint state model for `pending/running/completed/failed/cancelled`.
- [x] Add cancel/resume API surface.

## Day 7: Observability Baseline
- [x] Implement structured logger in `src/observability/logging.py`.
- [x] Implement timeline reconstruction in `src/observability/timeline.py`.
- [x] Add minimal metrics in `src/observability/metrics.py`:
  - [x] queue depth
  - [x] runtime latency
  - [ ] tool failure rate
  - [ ] retries
- [x] Ensure all runtime events include correlation IDs.

## Day 8: MCP Integration Baseline
- [x] Implement `src/mcp/mcp_registry.py`.
- [x] Implement `src/mcp/mcp_client_adapter.py`.
- [x] Implement `src/mcp/mcp_tool_adapter.py`.
- [x] Add trust tiers (`trusted`, `restricted`, `sandboxed`) and policy enforcement.

## First Vertical Slice (Must Pass)
- [ ] Host adapter receives input.
- [x] Orchestrator starts a session and selects runtime mode.
- [x] Runtime emits a tool request.
- [x] Deterministic tool runtime executes through policy/decorator chain.
- [x] Result is returned to runtime.
- [x] Structured logs + timeline show the full path with correlation IDs.

## Quality Gates Before Iterating
- [x] Unit tests for runtime mode selector and capability routing.
- [x] Unit tests for tool executor and decorators.
- [x] Integration test for one full turn with deterministic tool call.
- [x] Concurrency test with at least 5 parallel jobs.
- [x] Failure-path test: tool error -> retry/fallback -> auditable log.
- [x] MCP adapter test with one mocked MCP server.

## Non-Negotiable Rules
- [ ] No UI/controller logic inside core runtime modules.
- [x] No direct provider calls from orchestration core (only adapters).
- [x] No state-changing tool execution without policy gates.
- [x] No provider-native assumptions without capability map checks.
- [x] No silent failures (all failures must emit structured log events).

## Done Definition for Bootstrap
- [ ] New repo builds and runs tests.
- [ ] First vertical slice demo works end-to-end.
- [ ] Architecture boundaries are preserved by code layout and interfaces.
- [ ] `.cursor` docs and rules are present and used by agents.
- [ ] Team can begin feature work without revisiting core architecture assumptions.
