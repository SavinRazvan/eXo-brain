# MVP Build Sequence (2 Weeks)

## Goal
Build a working MVP for a modular, dynamic, multi-layer background agent system using OpenAI Agents SDK orchestration with deterministic local tool execution.

## Scope of MVP
- Background job submission and tracking.
- Task graph execution in sequential and parallel modes.
- Deterministic tool runtime with policy pre-check.
- OpenAI Agents runtime adapter.
- Basic plugin lifecycle (`load`, `unload`, `list`).
- Workflow loading from local JSON/YAML with schema validation.
- MCP server registration and MCP tool adapter support (initial subset).
- Checkpoint and resume for unfinished jobs.
- Structured logging + metrics + traces (parallel-safe).

## Week 1: Core Runtime Skeleton

### Day 1-2: Foundation and Contracts
Create:
- `src/schemas/events.py`
- `src/schemas/tool_io.py`
- `src/schemas/outputs.py`
- `src/core/session_store.py`
- `src/core/orchestrator.py`

Deliverables:
- Canonical datatypes for runtime events and tool envelopes.
- Session/job state model.
- Orchestrator interface stubs.

Acceptance:
- Unit tests for schema validation and state transitions.

### Day 3: Runtime Adapter Boundary
Create:
- `src/runtime/runtime_adapter.py`
- `src/runtime/openai_agents_runtime.py`

Deliverables:
- Adapter interface for session start, turn execution, and tool result submission.
- Adapter health and capability contract (`healthcheck`, `get_capabilities`).
- First OpenAI Agents SDK adapter implementation (minimal happy-path).

Acceptance:
- Integration test with mocked adapter events.
- Adapter contract test for capability + health responses.

### Day 4: Deterministic Tool Runtime
Create:
- `src/tools/descriptors.py`
- `src/tools/registry.py`
- `src/tools/executor.py`

Deliverables:
- Tool descriptor schema with risk and timeout metadata.
- Registry-based resolution (`tool_name -> descriptor -> callable`).
- Deterministic execution and normalized output envelope.

Acceptance:
- Tool execution tests (success, failure, unknown tool).

### Day 5: Policy Middleware
Create:
- `src/policies/middleware.py`
- `src/policies/risk_gates.py`

Deliverables:
- Pre-tool policy checks (deny/allow/escalate).
- Risk gate enforcement by tool metadata.

Acceptance:
- Tests for blocked risky tools and approved low-risk tools.

## Week 2: Background Execution + Plugins + Reliability

### Day 6-7: Task Graph and Scheduler
Create:
- `src/core/task_graph.py`
- `src/core/scheduler.py`
- `src/core/background_runtime.py`

Deliverables:
- DAG task representation.
- Sequential and parallel dispatch strategies.
- Background job submission/status APIs.

Acceptance:
- End-to-end test for multi-node graph execution.

### Day 8: Worker Pool and Concurrency Controls
Create:
- `src/core/worker_pool.py`
- `src/config/settings.py`

Deliverables:
- Bounded worker pool with max concurrency.
- Configurable queue/backpressure parameters.

Acceptance:
- Concurrency tests with bounded parallelism.

### Day 9: Checkpoint and Resume
Create:
- `src/core/checkpoint_store.py`

Deliverables:
- Persist node state and job progress.
- Resume unfinished jobs after restart simulation.

Acceptance:
- Restart/resume integration test.

### Day 10: Workflow Loader (MVP)
Create:
- `src/core/workflow_loader.py`
- `src/schemas/workflow_schema.py`

Deliverables:
- Load workflow definitions from local files.
- Version/schema compatibility checks before run.
- Workflow registry keyed by `workflow_id` and `version`.

Acceptance:
- Workflow load test passes for valid schema.
- Invalid schema/version fails with structured error.

### Day 11: Plugin Lifecycle (MVP)
Create:
- `src/tools/plugins/plugin_contract.py`
- `src/tools/plugins/plugin_manager.py`
- `src/tools/decorators.py`

Deliverables:
- Plugin manifest/contract.
- `load_plugin`, `unload_plugin`, `list_plugins`.
- Decorator hooks for validation/audit/security wrappers.
- Safety rule: block unload if active non-idempotent tasks exist.

Acceptance:
- Plugin lifecycle tests (load/unload/compatibility failure).
- Decorator chain test confirms security hooks cannot be bypassed.

### Day 12: MCP Integration (MVP subset)
Create:
- `src/mcp/mcp_registry.py`
- `src/mcp/mcp_client_adapter.py`
- `src/mcp/mcp_tool_adapter.py`

Deliverables:
- Register MCP servers (external/custom).
- Expose selected MCP tools through normalized tool descriptors.
- Enforce trust tier and timeout policy on MCP tool calls.

Acceptance:
- MCP server health check test passes.
- MCP tool call succeeds/fails with structured, auditable output.

### Day 13: Observability Baseline
Create:
- `src/observability/logging.py`
- `src/observability/tracing.py`
- `src/observability/metrics.py`

Deliverables:
- Correlation IDs per job/task/tool/plugin.
- Basic counters/timers (queue depth, success/failure, retries).
- Runtime timeline logs that reconstruct parallel execution per job.
- Log query API by `job_id`, `task_id`, `agent_id`, `tool_name`.
- Log query API by `mcp_server_id` and decorator hook.

Acceptance:
- Logs, traces, and metrics are emitted in integration tests.
- One failing parallel scenario is debuggable end-to-end from logs alone.

### Day 14: End-to-End Vertical Slice
Create:
- `tests/integration/test_background_agent_pipeline.py`
- `tests/integration/test_multi_adapter_workflow_parity.py` (initial OpenAI + one mock adapter)

Deliverables:
- One full scenario:
  - submit job
  - route to multiple agents
  - execute tool calls
  - enforce policy gates
  - complete and aggregate output

Acceptance:
- Test passes with deterministic outputs and stable runtime envelope.
- Same workflow contract passes on OpenAI adapter and mock/fallback adapter.

### Day 15: Hardening and Documentation
Create:
- `docs/architecture_mvp.md`
- `docs/runtime_contracts.md`
- `docs/plugin_lifecycle.md`
- `docs/workflow_loading.md`
- `docs/mcp_integration.md`

Deliverables:
- Documented architecture and contracts.
- Known limitations list for post-MVP iteration.

Acceptance:
- Team can run full integration suite and understand extension points.

## Minimal Backlog After MVP
- Adaptive autoscaling in `AgentScaler`.
- Dead-letter queue and circuit breaker policies.
- Advanced conflict resolution in `ResultAggregator`.
- Fine-grained tenancy and cost governance.

## References
- Upstream repository: https://github.com/SavinRazvan/flexiai-toolsmith
- Snapshot commit: `3f8b0c7a0996117dc95f0a8b93678dae44a5b0d6`
- Planning context:
  - https://github.com/SavinRazvan/flexiai-toolsmith/blob/3f8b0c7a0996117dc95f0a8b93678dae44a5b0d6/docs/ARCHITECTURE.md
  - https://github.com/SavinRazvan/flexiai-toolsmith/blob/3f8b0c7a0996117dc95f0a8b93678dae44a5b0d6/docs/WORKFLOW.md
  - https://github.com/SavinRazvan/flexiai-toolsmith/blob/3f8b0c7a0996117dc95f0a8b93678dae44a5b0d6/agents_experiments/OpenAI_AgentsSDK/test_runner.py
  - https://github.com/SavinRazvan/flexiai-toolsmith/blob/3f8b0c7a0996117dc95f0a8b93678dae44a5b0d6/agents_experiments/OpenAI_AgentsSDK/performance_monitoring.py
