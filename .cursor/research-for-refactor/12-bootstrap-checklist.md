# Bootstrap Checklist (Day 0 to First Vertical Slice)

## Goal
Provide a concrete startup checklist for creating the new repository and reaching a first working vertical slice fast, while preserving modular, dynamic, scalable architecture constraints.

## Inputs
- `02-target-architecture.md`
- `08-module-requirements-matrix.md`
- `10-provider-capability-matrix.md`
- `11-port-matrix.md`

## Day 0: Repository Initialization
- [x] Create new repository with Python project scaffolding (`src/`, `tests/`, `pyproject.toml`, `README.md`).
- [x] Add `.cursor/` portable pack into new repo root.
- [x] Create package structure:
  - [x] `src/integration`
  - [x] `src/core`
  - [x] `src/runtime`
  - [x] `src/agents`
  - [x] `src/tools`
  - [x] `src/mcp`
  - [x] `src/persistence`
  - [x] `src/policies`
  - [x] `src/schemas`
  - [x] `src/observability`
  - [x] `src/config`
- [x] Create test structure:
  - [x] `tests/modules`
  - [x] module-focused suites (for example `tests/modules/core`, `tests/modules/runtime`, `tests/modules/policies`)
  - [x] cross-cutting suites represented through module markers/layout

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
  - [x] fallback behavior
- [x] Add initial adapters:
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
- [x] Enforce deterministic execution for state-changing/high-impact calls.

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
  - [x] tool failure rate
  - [x] retries
- [x] Ensure all runtime events include correlation IDs.

## Day 8: MCP Integration Baseline
- [x] Implement `src/mcp/mcp_registry.py`.
- [x] Implement `src/mcp/mcp_client_adapter.py`.
- [x] Implement `src/mcp/mcp_tool_adapter.py`.
- [x] Add trust tiers (`trusted`, `restricted`, `sandboxed`) and policy enforcement.
- [x] Add per-server health controls integrated with MCP execution path.

## First Vertical Slice (Must Pass)
- [x] Host adapter receives input.
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
- [x] No UI/controller logic inside core runtime modules.
- [x] No direct provider calls from orchestration core (only adapters).
- [x] No state-changing tool execution without policy gates.
- [x] No provider-native assumptions without capability map checks.
- [x] No silent failures (all failures must emit structured log events).

## Done Definition for Bootstrap
- [x] New repo builds and runs tests.
- [x] First vertical slice demo works end-to-end.
- [x] Architecture boundaries are preserved by code layout and interfaces.
- [x] `.cursor` docs and rules are present and used by agents.
- [x] Team can begin feature work without revisiting core architecture assumptions.

## API Platform — Slice 0 (feature/api-platform)

### Pre-requisite Contract Changes
- [x] `ProviderRegistry.get_adapter(provider_id)` added to `src/config/provider_registry.py`
- [x] `AgentSpec.instructions: str = ""` added to `src/agents/contracts.py`
- [x] `ToolRegistry.list_descriptors()` added to `src/tools/registry.py`
- [x] `ToolDescriptor.description` + `parameters_schema` fields added
- [x] `ToolRegistry.unregister(tool_name)` added
- [x] `PluginManager.unload_plugin` updated to call `registry.unregister()` for each plugin tool

### New Files
- [x] `src/runtime/tool_wiring.py` — `build_agent_tools()` helper (late binding, adapter-only import)
- [x] `src/runtime/tenant_runtime.py` — `TenantRuntimeContext` + `TenantRuntimeFactory`

### Adapter Wiring
- [x] `src/runtime/openai_agents_runtime.py` — real OpenAI Agents SDK wiring via `build_agent_tools`
- [x] Legacy stub path (`planned_tool_call`) preserved for existing tests

### AgentRegistry
- [x] `list_routes()` added
- [x] `list_fallback_policies()` added

### Tests
- [x] `tests/modules/config/test_provider_registry.py` (3 tests — get_adapter)
- [x] `tests/modules/runtime/test_tenant_runtime.py` (27 tests — all Slice 0 acceptance gates)
- [x] Architecture gates pass: `validate_layers.py` + `scan_forbidden_imports.py`
- [x] Full test suite: 167 passed, 0 failed
