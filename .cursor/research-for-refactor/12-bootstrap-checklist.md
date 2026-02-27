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
- [ ] Add `.cursor/` portable pack into new repo root.
- [ ] Create package structure:
  - [ ] `src/integration`
  - [ ] `src/core`
  - [ ] `src/runtime`
  - [ ] `src/agents`
  - [ ] `src/tools`
  - [ ] `src/mcp`
  - [ ] `src/persistence`
  - [ ] `src/policies`
  - [ ] `src/schemas`
  - [ ] `src/observability`
  - [ ] `src/config`
- [ ] Create test structure:
  - [ ] `tests/integration`
  - [ ] `tests/regression`
  - [ ] `tests/performance`

## Day 1: Contracts First
- [ ] Define `RuntimeAdapter` contract in `src/runtime/runtime_adapter.py`.
- [ ] Define `ToolRuntime` contract in `src/tools/executor.py`.
- [ ] Define policy contract in `src/policies/middleware.py`.
- [ ] Define persistence contracts in `src/persistence/contracts.py`.
- [ ] Define typed event/output/tool schemas in `src/schemas/*`.
- [ ] Add provider capability schema in `src/runtime/capability_map.py`.

## Day 2: Provider and Mode Selection
- [ ] Implement `src/runtime/mode_selector.py` with policy-aware routing:
  - [ ] `provider_native`
  - [ ] `deterministic`
  - [ ] fallback behavior
- [ ] Add initial adapters:
  - [ ] `openai_agents_runtime.py`
  - [ ] `openai_compatible_runtime.py`
  - [ ] `custom_runtime.py`
- [ ] Add provider registry in `src/config/provider_registry.py`.
- [ ] Implement settings schema + startup validation in `src/config/settings.py` and `src/config/provider_registry.py` (see `34-provider-registry-and-settings-schema.md`).

## Day 3: Deterministic Tool Runtime
- [ ] Implement descriptor-based registry in `src/tools/registry.py`.
- [ ] Implement deterministic tool executor in `src/tools/executor.py`.
- [ ] Add plugin lifecycle API:
  - [ ] `load_plugin`
  - [ ] `unload_plugin`
  - [ ] `reload_plugin`
  - [ ] `validate_compatibility`
- [ ] Add standardized tool output envelope in `src/schemas/tool_io.py`.

## Day 4: Policy + Decorators + Safety
- [ ] Implement pre/post policy checks in `src/policies/middleware.py`.
- [ ] Add `src/tools/decorators.py` with hooks for:
  - [ ] validation
  - [ ] authz
  - [ ] retries
  - [ ] audit logging
  - [ ] redaction
- [ ] Enforce deterministic execution for risky/state-changing calls.

## Day 5: Core Orchestration + Event Routing
- [ ] Implement `src/core/orchestrator.py` with clear boundaries.
- [ ] Implement `src/core/event_router.py` (event map pattern).
- [ ] Implement session and correlation context in `src/core/session_context.py`.
- [ ] Ensure integration boundary in `src/integration/host_adapter.py` remains transport-agnostic.
- [ ] Implement persistence adapters in `src/persistence/adapters/` (`postgres`, `sqlite`) with parity tests.

## Day 6: Background Runtime Foundation
- [ ] Define `TaskGraph` model and scheduler contract.
- [ ] Implement initial bounded worker pool.
- [ ] Implement checkpoint state model for `pending/running/completed/failed/cancelled`.
- [ ] Add cancel/resume API surface.

## Day 7: Observability Baseline
- [ ] Implement structured logger in `src/observability/logging.py`.
- [ ] Implement timeline reconstruction in `src/observability/timeline.py`.
- [ ] Add minimal metrics in `src/observability/metrics.py`:
  - [ ] queue depth
  - [ ] runtime latency
  - [ ] tool failure rate
  - [ ] retries
- [ ] Ensure all runtime events include correlation IDs.

## Day 8: MCP Integration Baseline
- [ ] Implement `src/mcp/mcp_registry.py`.
- [ ] Implement `src/mcp/mcp_client_adapter.py`.
- [ ] Implement `src/mcp/mcp_tool_adapter.py`.
- [ ] Add trust tiers (`trusted`, `restricted`, `sandboxed`) and policy enforcement.

## First Vertical Slice (Must Pass)
- [ ] Host adapter receives input.
- [ ] Orchestrator starts a session and selects runtime mode.
- [ ] Runtime emits a tool request.
- [ ] Deterministic tool runtime executes through policy/decorator chain.
- [ ] Result is returned to runtime.
- [ ] Structured logs + timeline show the full path with correlation IDs.

## Quality Gates Before Iterating
- [ ] Unit tests for runtime mode selector and capability routing.
- [ ] Unit tests for tool executor and decorators.
- [ ] Integration test for one full turn with deterministic tool call.
- [ ] Concurrency test with at least 5 parallel jobs.
- [ ] Failure-path test: tool error -> retry/fallback -> auditable log.
- [ ] MCP adapter test with one mocked MCP server.

## Non-Negotiable Rules
- [ ] No UI/controller logic inside core runtime modules.
- [ ] No direct provider calls from orchestration core (only adapters).
- [ ] No state-changing tool execution without policy gates.
- [ ] No provider-native assumptions without capability map checks.
- [ ] No silent failures (all failures must emit structured log events).

## Done Definition for Bootstrap
- [ ] New repo builds and runs tests.
- [ ] First vertical slice demo works end-to-end.
- [ ] Architecture boundaries are preserved by code layout and interfaces.
- [ ] `.cursor` docs and rules are present and used by agents.
- [ ] Team can begin feature work without revisiting core architecture assumptions.
