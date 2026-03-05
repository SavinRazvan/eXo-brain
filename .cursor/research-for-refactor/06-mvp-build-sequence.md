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

## Implementation Status Snapshot

Legend: `Implemented`, `In Progress`, `Pending`.

| Area | Status | Notes |
|---|---|---|
| Day 1-2 foundation (`schemas`, `orchestrator`) | Implemented | `events.py`, `tool_io.py`, `orchestrator.py` are present with tests. |
| Day 3 adapter boundary | Implemented | `runtime_adapter.py`, `openai_agents_runtime.py`, adapter contract tests are present. |
| Day 4 deterministic tool runtime | Implemented | `registry.py` and `executor.py` implemented with success/failure test coverage. |
| Day 5 policy middleware | Implemented (MVP baseline) | Added `risk_gates.py` and middleware wiring for explicit `allow` / `deny` / `escalate` decisions with deterministic enforcement metadata. |
| Agents contracts baseline | Implemented (MVP baseline) | Added `src/agents/contracts.py`, `registry.py`, `plugin_contract.py`, and `plugin_manager.py`, then wired orchestrator handoff fallback routing with unit/integration coverage. |
| Provider settings + registry follow-up | Implemented | `config/settings.py`, `config/provider_registry.py` and startup validation are present. |
| Architecture fitness CI baseline | Implemented | workflow + architecture boundary scripts are present. |
| Week 2 background runtime primitives | Implemented | `task_graph`, `scheduler`, `worker_pool`, `checkpoint_store`, and `background_runtime` are implemented with checkpoint-aware execution. |
| Day 10 workflow loading contracts | Implemented | `workflow_schema.py` and `workflow_loader.py` are present with unit/integration validation coverage. |
| Scheduler replay + failure-path tests | Implemented | Added tests for resume replay, failure reason codes, retries, and bounded concurrency. |
| Observability baseline | Implemented (MVP baseline) | Added `observability/logging.py`, `timeline.py`, `metrics.py`, `tracing.py` and wired scheduler/background runtime structured emissions with correlation IDs and trace spans. |
| Plugin lifecycle/decorators | Implemented (MVP baseline) | Added plugin contract/manager (`load`, `unload`, `reload`, compatibility checks) plus execution decorators for validation/authz/retries/audit/redaction. |
| MCP baseline | Implemented (MVP baseline) | Added MCP registry/client/tool adapter with trust tiers, per-server health and timeout controls, and policy-aware execution plus integration tests with mocked MCP server calls. |
| Full background E2E vertical slice | Implemented (MVP baseline) | Added `tests/modules/core/test_background_agent_pipeline.py` to validate host input, multi-node background execution, deterministic tool execution, policy gating, and observability signals. |
| Enterprise modular safety slice | Implemented | Added identity/access-control/tenancy/secrets/resilience/audit/compliance modules, persistence store expansion, and broader replay/security/resilience/quality-gates test tracks. |
| API Platform — Slice 0 (tenant runtime isolation) | Implemented | `TenantRuntimeContext` + `TenantRuntimeFactory` (per-tenant registry isolation, per-session orchestrator); `build_agent_tools()` delegating wrapper; real OpenAI Agents SDK wiring promoted from notebooks into `OpenAIAgentsRuntimeAdapter`; `ProviderRegistry.get_adapter()`, `AgentSpec.instructions`, `ToolRegistry.list_descriptors/unregister`, `ToolDescriptor.description+parameters_schema` added. |
| API Platform — Slice 1 (FastAPI transport layer) | Implemented | `src/api/` directory: app factory, bootstrap, X-Identity auth middleware, Pydantic schemas for all domains, shared SSE/WebSocket event envelope; `scan_forbidden_imports.py` updated to allow `fastapi` in `src/api/`. |
| API Platform — Slice 2 (tool & agent management API) | Implemented | CRUD endpoints for tenant-scoped tools (`handler_ref` via importlib) and agents (with handoff routes and fallback policies). |
| API Platform — Slice 3 (adapter playground API) | Implemented | Session lifecycle, SSE turn streaming, WebSocket multi-turn with `asyncio.Task` cancellation, provider health/capabilities endpoints. |
| API Platform — Slice 4 (tenant policy & quota management) | Implemented | `GET/PUT /policy` (live overlay, no restart needed) + `GET/PUT /quota` (per-tenant job limit). `TenantQuotaManager.set_limit()` added. |
| CI hardening | Implemented | Added `fastapi`, `uvicorn[standard]`, `sse-starlette`, `websockets` to `requirements.txt`; fixed all three CI test jobs to install `requirements.txt` instead of minimal `pytest` only. 253 tests pass. |
| Platform Extensions — Slice 3 (Web UI dashboard) | Implemented | Added `/ui` static mount, modular TS source (`ui/src`), screen/components split, and build scripts generating and verifying synchronized `ui/dist` artifacts. |
| Tenant Tool Execution — Slice 2 hardening (runtime controls + transport propagation) | Implemented | Added process-isolation baseline, cancellation/control hooks, admin runtime-control APIs, canonical run-control registry, and SSE/WS cancellation forwarding with regression coverage. |
| Tenant Tool Execution — Slice 4.1 BYOC lease/replay hardening | Implemented | Added BYOC job queue lease contracts, lease timeout requeue behavior, JWT `jti` + request nonce replay protection, and integration coverage for retry + duplicate callback races. |
| Tenant Tool Execution — Slice 4.2 BYOC SQLite durability | Implemented | Added SQLite-backed BYOC queue/result/replay stores and restart-recovery tests validating cross-instance claim/submit completion. |
| Tenant Tool Execution — Slice 4.3 BYOC operational cleanup + metrics | Implemented | Added tenant-scoped retention cleanup hooks (queue/result/replay), periodic cleanup controls, cleanup API endpoint, and BYOC health metrics in runtime control stats. |
| Tenant Tool Execution — Slice 5.0 streaming tool state machine baseline | Implemented | Added provider-neutral `tool_progress` events, deterministic lifecycle state emission, SSE/WS envelope mapping, and cancellation call-id tracking from progress events. |
| Tenant Tool Execution — Slice 5.1 BYOC adapter-originated progress | Implemented | Added adapter-level progress drain hook and BYOC runtime state recording so orchestrator emits BYOC-sourced `queued/running/terminal` progress, with SSE/WS transition assertions. |
| Tenant Tool Execution — Slice 5.2 BYOC progress metadata + cancel race guarantees | Implemented | Added BYOC job/lease metadata in streamed `tool_progress` payloads and enforced cancel-path terminal guarantees for forced disconnect/late-cancel races across SSE/WS. |
| Tenant Tool Execution — Slice 5.3 in-flight cancelled progress + ordering guarantees | Implemented | Added explicit in-flight `tool_progress(cancelled)` emission on cancel requests and deterministic SSE/WS ordering so cancel progress is emitted before terminal cancel signaling. |
| Tenant Tool Execution — Slice 6.0 security/governance/scale baseline | Implemented | Added tool upload dependency/size/scan policy gates, tenant turn/upload rate limits and active-run concurrency caps, plus structured+persistent tool audit events for upload and throttling decisions. |
| Tenant Tool Execution — Slice 6.1 lifecycle governance + audit query/report APIs | Implemented | Added tool version deactivate/rollback/revoke governance endpoints, persisted lifecycle store operations, and tenant-scoped audit list/report APIs with coverage. |
| Tenant Tool Execution — Slice 6.2 audit export artifacts + retention controls | Implemented | Added tenant audit export bundle endpoint with tamper-evident chain validation and retention cleanup endpoint with configurable audit record caps. |
| Tenant Tool Execution — Slice 6.3 signed audit evidence + export-file verification workflow | Implemented | Added signed audit bundle generation/verification, export-to-file workflow, and admin verification endpoint for signature+chain validation over file or inline bundle payloads. |
| Tenant Tool Execution — Slice 6.4 audit signing operationalization (key rotation + signature versioning) | Implemented | Added active signing key version selection, versioned signing keyring config, and backward-compatible verification for both versioned and legacy unsigned-version bundles. |
| Tenant Tool Execution — Post 6.4 P0/P1/P2 gap closure track | Implemented | Completed `T1`-`T4`: tenant boundary enforcement, active uploaded-version runtime wiring, import-first Tool Manager baseline, and canonical docs synchronization. |
| Tenant Tool Execution — N1/N2/N3 follow-through | Implemented | Completed Tool Manager bundle upload UX + integrity visibility (N1), BYOC artifact-integrity parity (N2), and rollout/ops hardening with profile defaults + dashboard/runbook baselines + evidence linkage (N3). |
| RC signoff CI gate | Implemented | Added `.github/workflows/rc-signoff.yml` to run `make rc-signoff` and `make rc-signoff-json` on PRs to `main`, uploading both markdown and normalized JSON evidence artifacts. |
| RC signoff evidence metadata hardening | Implemented | `scripts/release/rc_signoff.py` now emits per-gate command/exit-code/duration metadata; `scripts/release/parse_rc_signoff.py` parses these fields with backward compatibility for prior markdown evidence format. |
| Backlog reconciliation freeze | Implemented | Added reconciled post-delivery hardening queue and evidence artifacts (`.local/alignment-audit.md`, `.local/alignment-todos.md`) and synced canonical status references. |
| P2 expansion webhook baseline | Implemented (baseline) | Added BYOC webhook submit endpoint and replay-safe auth flow for worker push result ingestion; P2 queue closure tracked in `docs/plans/p2-expansion-roadmap.md` and next queue planning tracked in `docs/plans/backlog-reconciliation-v2-execution-board.md`. |
| P2-1 autoscaling/backpressure baseline | Implemented (baseline) | Added `src/core/agent_scaler.py` plus background-runtime admission wiring for scale-up and deterministic backpressure thresholds, with unit/integration coverage in core runtime tests. |
| P2-2 DLQ/replay baseline | Implemented (baseline) | Added BYOC dead-letter routing on lease-attempt exhaustion plus runtime-control list/replay APIs and deterministic test coverage for replay back into successful completion. |
| P2-3 conflict-resolution baseline | Implemented (baseline) | Added strategy-driven BYOC result conflict resolution (`first_write_wins`, `last_write_wins`, `prefer_success`) with deterministic reject/replace reason codes and store-level conflict tests. |
| P2-4 tenancy/cost governance baseline | Implemented (baseline) | Added tenant-scoped BYOC cost/rejection counters with optional cost-limit enforcement gate and runtime-control metrics for dashboard/alert wiring. |
| P0-2 local-data durability baseline | Implemented (baseline) | Added `scripts/release/local_data_safety.py` backup/restore/validate commands, make targets (`db-backup`/`db-restore`/`db-validate`), recovery runbook steps, and script-level regression tests. |
| P0-3 RC signoff data-safety gate baseline | Implemented (baseline) | Added RC evidence `Local Data Safety` section and parser normalization (`data_safety`) with default advisory mode plus opt-in required blocking via `EXO_RC_SIGNOFF_REQUIRE_DATA_SAFETY=true`. |

Canonical reference for current status and pending order:
- `docs/plans/tenant-tool-execution-architecture.md` (`Canonical Current State (single source)`).

Hosted external beta evidence references:
- `docs/operations/release-candidate-signoff-checklist.md`
- `src/config/settings.py`
- `src/api/app.py`
- `tests/modules/api/test_deployment_profile_defaults.py`
- `docs/operations/byoc-artifact-integrity-dashboard.md`
- `.cursor/research-for-refactor/18-enterprise-operational-runbooks.md`
- `.cursor/research-for-refactor/26-deployment-profiles-matrix.md`

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
- Tests for blocked high-impact tools and approved low-risk tools.

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
- `tests/modules/core/test_background_agent_pipeline.py`
- `tests/modules/core/test_multi_adapter_workflow_parity.py` (initial OpenAI + one mock adapter)

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
