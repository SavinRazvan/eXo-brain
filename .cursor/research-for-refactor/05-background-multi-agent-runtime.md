# Background Multi-Agent Runtime

## Goal
Define a runtime model that supports dynamic, scalable, background execution of multiple agents, while keeping tool execution deterministic and policy-governed.

## Embedding Constraint
- The framework is delivered as an embeddable module/SDK.
- Host applications provide transport and UI/API concerns through integration adapters.
- Runtime transport remains optional (`SSE`, `WebSocket`, polling, queue workers), selected by host adapter needs.

## Why This Is Needed
- OpenAI Agents SDK orchestration can be effective, but background coordination requirements (parallel workers, retries, checkpointing, cancellation, adaptive scaling) must be explicit in your system design.
- Current FlexiAI baseline demonstrates mostly sequential tool execution in key paths, so the new architecture needs an explicit concurrency model.

## Runtime Building Blocks

### `TaskGraph`
- Represents a job as a DAG of tasks.
- Each node has:
  - `task_id`
  - `agent_role`
  - `dependencies`
  - `priority`
  - `timeout_s`
  - `retry_policy`
  - `budget_cost`

### `ExecutionPlanner`
- Converts user goal into executable `TaskGraph`.
- Chooses execution mode per stage:
  - `sequential`
  - `parallel`
  - `adaptive` (mode selected by load, risk, and budget)
- Must preserve KISS defaults: start with simple execution plans and enable adaptive complexity only when configured.

### `WorkflowLoader`
- Loads reusable workflow definitions from:
  - provider-exported workflow files (when available)
  - local file formats (JSON/YAML)
- Validates schema/version compatibility before execution.
- Supports hot reload for non-running workflow versions.

### `MCPServerManager`
- Registers and manages MCP server integrations.
- Supports:
  - external third-party MCP servers
  - organization-owned custom MCP servers
  - per-server capability and trust metadata
- Provides connection health monitoring and fallback behavior.

### `AgentWorkerPool`
- Executes `TaskGraph` nodes using worker processes/coroutines.
- Must support:
  - max concurrency per tenant/session
  - queue priorities
  - backpressure
  - graceful shutdown and drain

### `BudgetManager`
- Enforces token, cost, time, and tool-call limits.
- Can throttle or stop expansion when limits are hit.

### `CheckpointStore`
- Persists workflow snapshots and node states:
  - `pending`
  - `running`
  - `completed`
  - `failed`
  - `cancelled`
- Enables resume after crash/redeploy.

### `ResultAggregator`
- Merges outputs from multiple agents.
- Applies conflict resolution strategy:
  - confidence-weighted merge
  - domain-priority merge
  - escalate to reviewer agent

### `LoggingAndTraceStore`
- Captures all runtime events with strict ordering metadata.
- Required fields for each event:
  - `timestamp_utc`
  - `job_id`
  - `task_id`
  - `worker_id`
  - `agent_id`
  - `plugin_id`
  - `tool_name`
  - `run_mode` (`provider_native` | `deterministic`)
  - `event_type`
  - `status`
  - `latency_ms`
  - `error_code` (nullable)
- Must support high-concurrency, append-only writes.

## Core Interfaces

### `BackgroundRuntime`
- `submit_job(spec: JobSpec) -> JobHandle`
- `get_job_status(job_id: str) -> JobStatus`
- `cancel_job(job_id: str) -> bool`
- `resume_job(job_id: str) -> JobHandle`
- `stream_job_events(job_id: str) -> AsyncIterator[RuntimeEvent]`
- `load_workflow(source: WorkflowSource) -> WorkflowHandle`
- `register_mcp_server(config: MCPServerConfig) -> MCPServerHandle`

### `TaskScheduler`
- `schedule(graph: TaskGraph) -> SchedulePlan`
- `dispatch_next(worker_pool: AgentWorkerPool) -> list[TaskAssignment]`
- `rebalance(load: RuntimeLoad) -> RebalanceAction`

### `AgentScaler`
- `spawn(agent_profile: AgentProfile, count: int) -> list[WorkerId]`
- `retire(worker_ids: list[WorkerId]) -> bool`
- `recommend_scale(metrics: RuntimeMetrics) -> ScaleDecision`

### `RuntimeLogger`
- `log(event: RuntimeLogEvent) -> None`
- `log_error(event: RuntimeLogEvent, exc: Exception) -> None`
- `flush(job_id: str) -> None`
- `get_timeline(job_id: str) -> list[RuntimeLogEvent]`

## Plugin Plug-In / Plug-Out Lifecycle

### Plugin Contract
- `plugin_id`
- `version`
- `capabilities`
- `tool_descriptors`
- `policy_requirements`
- `healthcheck()`
- `mcp_capabilities` (optional)
- `decorator_hooks` (optional)

### Lifecycle API
- `load_plugin(manifest_path: str) -> PluginLoadResult`
- `unload_plugin(plugin_id: str) -> bool`
- `reload_plugin(plugin_id: str) -> PluginLoadResult`
- `list_plugins() -> list[PluginInfo]`
- `validate_compatibility(plugin_id: str, runtime_version: str) -> CompatibilityResult`
- `attach_decorator(plugin_id: str, hook: DecoratorHook) -> bool`
- `detach_decorator(plugin_id: str, hook_name: str) -> bool`

### Safety Rules
- Do not allow unload while plugin has active non-idempotent tasks.
- Require policy validation before plugin activation.
- Record audit events for all lifecycle operations.
- Enforce trust policy for MCP servers (`trusted`, `restricted`, `sandboxed`).
- Apply decorator order control to prevent bypassing security middleware.

## Concurrency and Reliability Policies

## Default Policy Set
- Max workers per job: configurable by tier.
- Max concurrent risky tools: 1 per session by default.
- Retry strategy: exponential backoff with capped attempts.
- Circuit breaker for repeatedly failing tools/plugins.
- Dead-letter queue for exhausted failures.

## Failure Recovery
- On worker failure, task is re-queued if idempotent.
- On orchestrator restart, `CheckpointStore` resumes unfinished jobs.
- On plugin failure, route to fallback plugin or safe degraded mode.

## Observability Requirements
- Correlation IDs across:
  - job
  - task
  - agent worker
  - tool call
  - plugin
- Mandatory log dimensions:
  - execution mode (`provider_native` / `deterministic`)
  - scheduler decision reason
  - plugin version
  - retry attempt
  - policy decision (`allow`/`deny`/`escalate`)
- Required metrics:
  - queue depth
  - scheduling latency
  - task success/failure rate
  - retry count
  - plugin failure rate
  - cost per job

## Debugging Requirements
- Provide a `job timeline` view that reconstructs end-to-end execution across parallel workers.
- Every error must include:
  - origin module
  - correlation IDs
  - normalized error category
  - retry/fallback action taken
- Support log search by `job_id`, `task_id`, `agent_id`, and `tool_name`.
- Support log search by `mcp_server_id` and `decorator_name`.
- Keep logging overhead bounded with async buffered writers.

## Execution Modes and Decision Rules

### Sequential Mode
- Use for strict dependency chains or high-risk operations.

### Parallel Mode
- Use for independent subtasks with bounded side effects.

### Adaptive Mode
- Use when runtime can optimize for SLA and budget:
  - increase parallelism when queue grows and error rates are low
  - reduce parallelism when failures/cost exceed thresholds

## Recommended Initial Implementation Order
1. `TaskGraph` + `BackgroundRuntime` APIs
2. `CheckpointStore` + resume/cancel semantics
3. `TaskScheduler` with sequential and parallel modes
4. `AgentWorkerPool` with bounded concurrency
5. `WorkflowLoader` + workflow schema/version validation
6. `MCPServerManager` + MCP trust policies
7. `LoggingAndTraceStore` + `RuntimeLogger`
8. Plugin lifecycle APIs + decorator hooks
9. Adaptive scaling and advanced rebalancing

## References
- Upstream repository: https://github.com/SavinRazvan/flexiai-toolsmith
- Snapshot commit: `3f8b0c7a0996117dc95f0a8b93678dae44a5b0d6`
- Sequential baseline and event orchestration references:
  - https://github.com/SavinRazvan/flexiai-toolsmith/blob/3f8b0c7a0996117dc95f0a8b93678dae44a5b0d6/flexiai/core/handlers/event_handler.py
  - https://github.com/SavinRazvan/flexiai-toolsmith/blob/3f8b0c7a0996117dc95f0a8b93678dae44a5b0d6/flexiai/core/handlers/tool_call_executor.py
  - https://github.com/SavinRazvan/flexiai-toolsmith/blob/3f8b0c7a0996117dc95f0a8b93678dae44a5b0d6/flexiai/core/events/sse_manager.py
  - https://github.com/SavinRazvan/flexiai-toolsmith/blob/3f8b0c7a0996117dc95f0a8b93678dae44a5b0d6/flexiai/core/events/rolling_event_buffer.py
