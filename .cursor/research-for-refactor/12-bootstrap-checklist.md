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
- [x] Full test suite: 167 passed, 0 failed (at Slice 0 merge)

---

## API Platform — Slice 1 (Transport Layer)

### New directory: `src/api/`
- [x] `src/api/app.py` — FastAPI app factory (`create_app()`)
- [x] `src/api/bootstrap.py` — wire `ProviderRegistry`, `TenantRuntimeFactory`, `TenantPolicyOverlayStore` into `app.state`
- [x] `src/api/dependencies.py` — `Depends()` providers: `get_identity`, `require_valid_identity`, `get_tenant_context`, `get_policy_overlay_store`
- [x] `src/api/middleware/auth.py` — `X-Identity` header → `IdentityContext` (plain JSON MVP; JWT upgrade path = swap this file only)
- [x] `src/api/schemas/tool_schemas.py` — `ToolRegisterRequest`, `ToolResponse`, `ToolListResponse`
- [x] `src/api/schemas/agent_schemas.py` — `AgentRegisterRequest`, `AgentResponse`, handoff/fallback schemas
- [x] `src/api/schemas/session_schemas.py` — `SessionCreateRequest`, `SessionCreateResponse`, `SessionStateResponse`
- [x] `src/api/schemas/turn_schemas.py` — shared SSE + WebSocket event envelope (`output_delta`, `tool_call`, `tool_result`, `run_complete`, `error`, `run_cancelled`)
- [x] `src/api/schemas/provider_schemas.py` — `ProviderSummaryResponse`, `ProviderHealthResponse`, `ProviderCapabilitiesResponse`
- [x] `scripts/architecture/scan_forbidden_imports.py` — updated to allow `fastapi` imports in `src/api/` layer

### Tests
- [x] `tests/modules/api/test_slice1_transport.py` (20 tests — app startup, auth, identity, tenant context)
- [x] Architecture gates pass after scan_forbidden_imports.py update

---

## API Platform — Slice 2 (Tool & Agent Management API)

### New files
- [x] `src/api/routers/tools.py` — `POST/GET/GET/{name}/DELETE /tenants/{id}/tools` (importlib `handler_ref` resolution at registration time)
- [x] `src/api/routers/agents.py` — `POST/GET/GET/{id}/DELETE /tenants/{id}/agents` + `POST/GET /routes` + `POST/GET /fallback`
- [x] Route ordering fixed: `/routes` and `/fallback` defined before `/{agent_id}` to prevent path-param collision

### Tests
- [x] `tests/modules/api/test_slice2_tools_agents.py` (28 tests — CRUD, handler_ref validation, tenant isolation, routes/fallback)

---

## API Platform — Slice 3 (Adapter Playground API)

### New files
- [x] `src/api/routers/sessions.py` — `POST /sessions` (creates session + wires host adapter), `GET /sessions/{id}`
- [x] `src/api/routers/turns.py` — `POST .../turns` (SSE streaming) + `WS .../ws` (WebSocket, multi-turn, cancellation via `asyncio.Task`)
- [x] `src/api/routers/providers.py` — `GET /providers`, `GET /providers/{id}/health`, `GET /providers/{id}/capabilities`

### Tests
- [x] `tests/modules/api/test_slice3_playground.py` (21 tests — session lifecycle, SSE event order, WebSocket turns, cancellation, provider endpoints)

---

## API Platform — Slice 4 (Tenant Policy Management)

### Contract changes
- [x] `TenantQuotaManager.set_limit(max_active_jobs)` added — validates non-negative, takes effect on next `check_submission`
- [x] `TenantQuotaManager.max_active_jobs` property added

### New files
- [x] `src/api/schemas/tenant_schemas.py` — `PolicyOverlayRequest/Response`, `QuotaResponse`, `QuotaUpdateRequest`
- [x] `src/api/routers/tenants.py` — `GET/PUT /tenants/{id}/policy` + `GET/PUT /tenants/{id}/quota`

### Tests
- [x] `tests/modules/api/test_slice4_tenant_policy.py` (17 tests — GET/PUT round-trips, per-tenant isolation, auth gates, overwrite semantics, negative quota rejection)

---

## CI Fix (fix/ci-missing-deps — PR #29)

- [x] `requirements.txt` — added `fastapi`, `uvicorn[standard]`, `sse-starlette`, `websockets`
- [x] `.github/workflows/architecture-fitness.yml` — replaced `pip install pytest pyyaml` with `pip install -r requirements.txt` in all three test jobs (`automated_test_suite`, `contract_tests`, `integration_architecture_fitness`)
- [x] Full test suite after all slices: **253 passed, 0 failed**

---

## Platform Extensions — Slice 2 (Dynamic Provider Registration — branch: feature/slice2-dynamic-provider-registration)

### Adapter factory
- [x] `src/runtime/adapter_factory.py` — `load_adapter(class_ref, provider_id, **kwargs)` via importlib

### ProviderRegistry mutable API
- [x] `src/config/provider_registry.py` — `register(record, adapter)`, `unregister(provider_id)`

### Provider persistence
- [x] `src/persistence/contracts.py` — `PersistedProviderRecord` dataclass, `ProviderStore` ABC
- [x] `src/persistence/adapters/sqlite.py` — `SQLiteProviderStore` (save, get, delete, list)

### SessionStore extension
- [x] `src/persistence/contracts.py` — `SessionStore.count_active_sessions_by_provider(provider_id)`
- [x] `src/persistence/adapters/sqlite.py`, `src/core/session_store.py`, `postgres.py` — implementations

### Provider router
- [x] `src/api/schemas/provider_schemas.py` — `ProviderRegisterRequest`, `ProviderRegisterResponse`
- [x] `src/api/routers/providers.py` — `POST /providers`, `DELETE /providers/{id}` (409 if active sessions)

### Bootstrap / startup
- [x] `src/api/bootstrap.py` — `provider_store`, `session_store` on app.state; `SQLiteProviderStore`
- [x] `src/api/startup.py` — hydrate providers from store on startup

### Tests
- [x] `tests/modules/api/test_slice_provider_registration.py` (8 tests — CRUD, 409, 404, 422, 503, restart)
- [x] Full test suite: **309 passed, 0 failed** (+8 new tests)

---

## Platform Extensions — Slice 3 (Web UI Dashboard — branch: feature/slice3-web-ui-dashboard)

### API static mount wiring
- [x] `src/api/routers/ui.py` — `mount_ui(app)` mounting `ui/dist` under `/ui`
- [x] `src/api/app.py` — invokes `mount_ui(app)` in app factory

### Dashboard artifact (prebuilt static bundle)
- [x] `ui/dist/index.html` — app shell with Tool/Agent/Provider/Playground screens
- [x] `ui/dist/app.js` — API client + CRUD flows + SSE/WebSocket playground wiring
- [x] `ui/dist/styles.css` — baseline dashboard styling

### TypeScript source modularization + build
- [x] `ui/src/api.ts` — typed(compatible) fetch/auth helpers
- [x] `ui/src/screens/tools.ts`, `ui/src/screens/agents.ts`, `ui/src/screens/providers.ts`, `ui/src/screens/playground.ts`
- [x] `ui/src/components/chat.ts` — shared chat/trace rendering helpers
- [x] `ui/src/app.ts` — entrypoint orchestration and navigation
- [x] `ui/tsconfig.json` and `ui/package.json` — TypeScript project configuration
- [x] `scripts/ui/build.sh` — build entrypoint (`tsc` when available, fallback transpiler otherwise)
- [x] `scripts/ui/build_ts_fallback.py` — environment-safe fallback `*.ts -> *.js` copier
- [x] `Makefile` — `make ui-build`, `make ui-verify`
- [x] `scripts/ui/verify_dist_sync.sh` — drift check between `ui/src` and `ui/dist`
- [x] `.github/workflows/architecture-fitness.yml` — adds `ui_dist_sync` CI gate

### Tests
- [x] `tests/modules/api/test_ui_static.py` — validates `/ui/`, `/ui/app.js`, `/ui/styles.css` are served

---

## Tenant Tool Execution — Slice 2 Hardening (hosted runtime controls)

### Runtime controls + isolation hardening
- [x] `src/tools/sandbox/runtime.py` — process-isolated execution option, cancellation token hooks, control stats
- [x] `src/tools/sandbox/process_runner.py` — process runner baseline with timeout terminate/kill semantics
- [x] `src/tools/sandbox/pool.py` — cleanup counters/events and eviction-reason observability
- [x] `src/tools/execution_adapter.py` — optional control hooks (`request_cancellation`, `control_stats`, `cleanup_events`)
- [x] `src/tools/executor.py` — adapter getter for control-plane integrations

### API/runtime orchestration controls
- [x] `src/api/routers/runtime_control.py` — admin endpoints for stats, cleanup events, call/run cancellation
- [x] `src/api/schemas/runtime_control_schemas.py` — typed control-plane responses/requests
- [x] `src/core/run_control_registry.py` — canonical run lifecycle registry (tenant/session/run/call/status)
- [x] `src/api/routers/turns.py` — run registry updates + SSE/WS cancellation forwarding via call_ids
- [x] `src/api/bootstrap.py` — app-scoped run control registry wiring

### Tests
- [x] `tests/modules/tools/test_sandbox_runtime.py` — timeout/cancel/failure-recovery/concurrency/process-mode coverage
- [x] `tests/modules/tools/test_sandbox_pool.py` — LRU/idle/cleanup counters/events coverage
- [x] `tests/modules/api/test_runtime_control_api.py` — control-plane endpoint coverage
- [x] `tests/modules/api/test_slice3_playground.py` — transport cancellation propagation + run registry assertions

---

## Tenant Tool Execution — Slice 4.1 Hardening (BYOC lease + replay)

### BYOC queue/lease/runtime controls
- [x] `src/tools/byoc/job_store.py` — durable queue/lease contract + in-memory adapter with claim/requeue semantics
- [x] `src/tools/byoc/connector_runtime.py` — lease-aware claim/submit flow, lease timeout requeue polling, and cancellation forwarding
- [x] `src/tools/byoc/job_contracts.py` — lease fields (`lease_token`, `lease_expires_at_epoch`, `claim_attempt`)

### Replay/idempotency controls
- [x] `src/tools/byoc/worker_auth.py` — short-lived JWTs with required `jti` claim
- [x] `src/tools/byoc/result_store.py` — idempotent result store + replay guard (`nonce/jti`) support
- [x] `src/api/routers/runtime_control.py` — BYOC claim/submit nonce enforcement through control plane

### Tests
- [x] `tests/modules/tools/test_byoc_runtime.py` — lease expiry reclaim, replay nonce rejection, duplicate callback race coverage
- [x] `tests/modules/api/test_byoc_runtime_control_api.py` — BYOC API replay and duplicate-submit behavior
- [x] `tests/modules/runtime/test_tenant_runtime.py` — hosted-default vs explicit BYOC runtime selection

---

## Tenant Tool Execution — Slice 4.2 Durability (BYOC sqlite persistence)

### SQLite durability adapters
- [x] `src/tools/byoc/sqlite_store.py` — SQLite BYOC job queue, result store, and replay guard adapters
- [x] `src/tools/byoc/result_store.py` — one-shot result consumption contract for cross-instance completion
- [x] `src/tools/byoc/connector_runtime.py` — result-store polling path for restart-safe BYOC execution flow

### Runtime wiring
- [x] `src/config/settings.py` — BYOC persistence backend/path/ttl settings (`byoc_store_backend`, `byoc_sqlite_db_path`, lease/replay ttl)
- [x] `src/api/app.py` — env wiring for BYOC sqlite runtime options
- [x] `src/runtime/tenant_runtime.py` — sqlite BYOC store injection when configured

### Tests
- [x] `tests/modules/tools/test_byoc_sqlite_recovery.py` — restart-recovery, lease requeue, replay persistence checks
- [x] `tests/modules/tools/test_byoc_runtime.py` — regression coverage on in-memory + durable-compatible runtime behavior
- [x] `tests/modules/runtime/test_tenant_runtime.py` — sqlite-backed BYOC runtime selection assertion

---

## Tenant Tool Execution — Slice 4.3 Operations (cleanup/retention + health metrics)

### Runtime/store cleanup + retention hooks
- [x] `src/tools/byoc/job_store.py` — tenant-scoped `health_metrics()` and `cleanup_retention()` contracts + in-memory implementation
- [x] `src/tools/byoc/result_store.py` — result/replay health + retention hook contracts
- [x] `src/tools/byoc/sqlite_store.py` — tenant-safe retention pruning for jobs/results/replay keys
- [x] `src/tools/byoc/connector_runtime.py` — periodic cleanup hook + explicit cleanup control + aggregated cleanup counters

### API/config/runtime wiring
- [x] `src/api/routers/runtime_control.py` — `POST /admin/byoc/cleanup` endpoint and tenant-scoped BYOC stats in `control-stats`
- [x] `src/api/schemas/runtime_control_schemas.py` — `ByocCleanupRequest/Response`
- [x] `src/config/settings.py` — BYOC retention interval/TTL/cap settings
- [x] `src/api/app.py` — env wiring for BYOC cleanup/retention settings
- [x] `src/runtime/tenant_runtime.py` — retention settings wired into BYOC runtime adapter

### Tests
- [x] `tests/modules/tools/test_byoc_sqlite_recovery.py` — tenant-scoped cleanup retention and bounded pruning checks
- [x] `tests/modules/api/test_byoc_runtime_control_api.py` — BYOC cleanup endpoint + runtime health metric assertions

---

## Tenant Tool Execution — Slice 5.0 Streaming State Machine (baseline)

### Runtime/transport lifecycle events
- [x] `src/schemas/events.py` — added `tool_progress` runtime event contract
- [x] `src/core/orchestrator.py` — deterministic tool lifecycle state emissions (`queued/running/terminal`)
- [x] `src/api/routers/turns.py` — SSE/WS mapping for `tool_progress` + call-id tracking for cancellation forwarding
- [x] `src/api/schemas/turn_schemas.py` — `ToolProgressEvent` envelope

### Tests
- [x] `tests/modules/core/test_orchestrator_turn.py` — deterministic tool progress state machine assertion
- [x] `tests/modules/api/test_slice3_playground.py` — runtime-event mapping + websocket cancel forwarding from `tool_progress`

---

## Tenant Tool Execution — Slice 5.1 BYOC adapter-originated progress events

### Adapter/orchestration wiring
- [x] `src/tools/execution_adapter.py` — added `drain_progress_events(call_id)` hook
- [x] `src/tools/byoc/connector_runtime.py` — records BYOC lifecycle progress (`queued/running/terminal`) for adapter-originated emission
- [x] `src/core/orchestrator.py` — consumes adapter progress events for BYOC calls and emits `tool_progress` from adapter path

### Tests
- [x] `tests/modules/core/test_orchestrator_turn.py` — BYOC adapter progress sequence assertion
- [x] `tests/modules/api/test_slice3_playground.py` — SSE/WS ordered `tool_progress` transition assertions

---

## Tenant Tool Execution — Slice 5.2 BYOC metadata streaming + cancel race guarantees

### BYOC progress metadata
- [x] `src/schemas/events.py` — `tool_progress` payload includes `job_id`, `lease_token`, `lease_expires_at_epoch`, `claim_attempt`
- [x] `src/tools/byoc/connector_runtime.py` — BYOC progress recorder attaches lease/job metadata across queued/running/terminal states
- [x] `src/core/orchestrator.py` — adapter-originated progress relay preserves BYOC metadata fields
- [x] `src/api/routers/turns.py` / `src/api/schemas/turn_schemas.py` — SSE/WS event mapping/schema include BYOC metadata

### Cancel/disconnect terminal guarantees
- [x] `src/api/routers/turns.py` — non-terminal guard helper prevents late-cancel overwrite of already-completed runs
- [x] `src/api/routers/turns.py` — forced disconnect/cancel paths mark terminal cancelled state deterministically when run is still active

### Tests
- [x] `tests/modules/tools/test_byoc_runtime.py` — adapter progress metadata assertions
- [x] `tests/modules/core/test_orchestrator_turn.py` — BYOC progress sequence with lease metadata
- [x] `tests/modules/api/test_slice3_playground.py` — runtime-event metadata mapping + forced disconnect/late-cancel race coverage

---

## Tenant Tool Execution — Slice 5.3 in-flight cancelled progress + ordering guarantees

### Cancellation progress emission
- [x] `src/api/routers/turns.py` — added explicit cancelled `tool_progress` event emission for active `call_id`s when run cancel is requested in-flight
- [x] `src/api/routers/turns.py` — WebSocket cancel path now emits ordered `tool_progress(cancelled)` before terminal `run_cancelled`
- [x] `src/api/routers/turns.py` — SSE stream path now emits `tool_progress(cancelled)` on in-flight cancel and suppresses late terminal run event forwarding

### Tests
- [x] `tests/modules/api/test_slice3_playground.py` — SSE in-flight cancellation ordering assertion
- [x] `tests/modules/api/test_slice3_playground.py` — WebSocket cancel-path cancelled progress ordering assertions

---

## Tenant Tool Execution — Slice 6.0 security/governance/scale baseline

### Tool package policy controls
- [x] `src/policies/tool_package_policy.py` — dependency token blocking + optional allowlist enforcement
- [x] `src/api/routers/tools.py` — artifact size gate + package_ref scan + validation integration
- [x] `src/api/schemas/tool_schemas.py` — `artifact_size_bytes` request field for upload-size enforcement

### Tenant rate/concurrency controls
- [x] `src/tenancy/rate_limiter.py` — process-local per-tenant fixed-window limiter
- [x] `src/api/bootstrap.py` — wired tenant turn/upload limiters from settings
- [x] `src/api/routers/turns.py` — SSE/WS turn rate + active-run concurrency enforcement
- [x] `src/core/run_control_registry.py` — active run count helper for concurrency gating

### Audit pipeline baseline
- [x] `src/observability/tool_audit.py` — structured + persisted tool audit emission
- [x] `src/api/bootstrap.py` — app-scoped audit pipeline/store/logger wiring
- [x] `src/api/routers/tools.py` / `src/api/routers/turns.py` — audit events on upload and limit rejections

### Tests
- [x] `tests/modules/api/test_tool_version_api.py` — artifact-size, dependency-allowlist, and upload-rate-limit coverage
- [x] `tests/modules/api/test_slice3_playground.py` — turn concurrency/rate-limit coverage on SSE/WS

---

## Tenant Tool Execution — Slice 6.1 lifecycle governance + audit query/report APIs

### Lifecycle governance endpoints
- [x] `src/api/routers/tools.py` — deactivate active version endpoint
- [x] `src/api/routers/tools.py` — rollback endpoint to switch active version
- [x] `src/api/routers/tools.py` — revoke package version endpoint with active-version guard/force option
- [x] `src/api/schemas/tool_schemas.py` — governance request/response schemas

### Persistence contracts/adapters
- [x] `src/persistence/contracts.py` — `ToolVersionStore` lifecycle methods (`clear_active_tool_version`, `delete_tool_version`)
- [x] `src/persistence/adapters/sqlite.py` — SQLite lifecycle method implementations

### Audit query/report APIs
- [x] `src/api/routers/audit.py` — tenant audit list/query/report endpoints
- [x] `src/api/schemas/audit_schemas.py` — audit response schemas
- [x] `src/persistence/contracts.py` / `src/persistence/audit_store.py` — audit list contract + in-memory implementation
- [x] `src/api/app.py` — audit router wiring

### Tests
- [x] `tests/modules/api/test_tool_version_api.py` — lifecycle governance endpoint coverage
- [x] `tests/modules/api/test_audit_api.py` — audit query/report endpoint coverage

---

## Tenant Tool Execution — Slice 6.2 audit export artifacts + retention controls

### Audit export bundle
- [x] `src/api/routers/audit.py` — export endpoint with deterministic hash-chain validation
- [x] `src/api/schemas/audit_schemas.py` — export bundle response schema
- [x] `src/audit/trail.py` reuse — tamper-evident chain helpers applied to exported records

### Audit retention controls
- [x] `src/persistence/contracts.py` / `src/persistence/audit_store.py` — audit cleanup contract + implementation
- [x] `src/api/routers/audit.py` — cleanup endpoint for tenant-scoped retention pruning
- [x] `src/config/settings.py` — audit retention/export limits

### Tests
- [x] `tests/modules/api/test_audit_api.py` — export chain-valid assertions + cleanup prune behavior

---

## Tenant Tool Execution — Slice 6.3 signed audit evidence + export-file verification workflow

### Signed evidence bundle support
- [x] `src/compliance/evidence_bundle.py` — deterministic bundle signing + signature verification helpers
- [x] `src/api/schemas/audit_schemas.py` — signed export/verify request-response schemas

### Export-to-file + verification APIs
- [x] `src/api/routers/audit.py` — `POST /admin/audit/export-file` writes signed bundle JSON into configured export directory
- [x] `src/api/routers/audit.py` — `POST /admin/audit/verify` validates signature + chain for file or inline bundle payload
- [x] `src/api/routers/audit.py` — export directory boundary checks block traversal outside configured root

### Config
- [x] `src/config/settings.py` / `src/api/app.py` — `audit_export_directory` + `audit_bundle_signing_secret` settings and env wiring

### Tests
- [x] `tests/modules/api/test_audit_api.py` — export-file success + verify success + tampered bundle verify-failure coverage

---

## Tenant Tool Execution — Slice 6.4 audit signing key rotation + signature-version verification

### Signing key rotation controls
- [x] `src/compliance/evidence_bundle.py` — versioned signing keyring + active signing key resolution helpers
- [x] `src/config/settings.py` / `src/api/app.py` — `audit_bundle_signing_active_version` + `audit_bundle_signing_secrets_by_version` config/env wiring

### Backward-compatible verification
- [x] `src/api/routers/audit.py` — verify supports explicit `signature_version` and legacy bundles without version field
- [x] `src/api/schemas/audit_schemas.py` — export/verify response metadata includes signature-version details

### Tests
- [x] `tests/modules/api/test_audit_api.py` — rotated key verification + legacy no-version signature compatibility coverage

---

## Tenant Tool Execution — Post 6.4 and N-track follow-through

Canonical reference:
- `docs/plans/tenant-tool-execution-architecture.md` (`Canonical Current State (single source)`).

### Completed: Post-6.4 gap-closure track (`T1`-`T4`)
- [x] Add shared tenant-scope guard to enforce `identity.tenant_id == path tenant_id` on tenant-scoped APIs.
- [x] Add explicit, role-gated super-admin bypass only if intentionally enabled.
- [x] Add API tests for same-tenant allow + cross-tenant deny (+ override path if enabled).
- [x] Wire active `ToolVersionStore` entries into hosted/BYOC runtime execution selection.
- [x] Ensure turns execute active uploaded versions, not only legacy registry `handler_ref` descriptors.
- [x] Add end-to-end tests: upload -> activate -> execute -> rollback -> execute prior version.
- [x] Make UI default flow: `import-schema` -> `upload` -> `validate` -> `versions`.
- [x] Add red/amber/green validation badges + active version visibility in UI.
- [x] Add browser/UI tests for validation-state transitions and happy-path flow.
- [x] Remove or relabel stale "next implementation slice" markers where superseded.
- [x] Maintain one canonical current-state section and reference it from companion plans.

### Completed: N1/N2/N3 follow-through
- [x] N1: Tool Manager bundle upload UX + artifact integrity visibility.
- [x] N2: BYOC claim/result artifact-integrity parity with deterministic rejection codes.
- [x] N3: rollout/operations hardening:
  - [x] deployment-profile defaults for artifact/audit/BYOC settings
  - [x] BYOC integrity dashboard baseline
  - [x] integrity mismatch + signing key-rotation operational runbooks
  - [x] companion tracker sync and hosted external beta evidence linkage

### Hosted external beta evidence links
- `docs/operations/release-candidate-signoff-checklist.md`
- `scripts/release/rc_signoff.py`
- `scripts/release/parse_rc_signoff.py`
- `src/config/settings.py`
- `src/api/app.py`
- `tests/modules/api/test_deployment_profile_defaults.py`
- `docs/operations/byoc-artifact-integrity-dashboard.md`
- `.cursor/research-for-refactor/18-enterprise-operational-runbooks.md`
- `.cursor/research-for-refactor/26-deployment-profiles-matrix.md`

### Reconciliation artifacts
- `.local/alignment-audit.md`
- `.local/alignment-todos.md`

### P2 expansion progress
- [x] P2-1 baseline completed: autoscaling/backpressure policy scaffolding (`AgentScaler`) wired into background runtime submission path with deterministic threshold tests.
- [x] P2-2 baseline completed: BYOC dead-letter routing + replay workflow (`/admin/byoc/dlq` list and replay API) with lease-exhaustion and replay-success coverage.
- [x] P2-3 baseline completed: BYOC result conflict-resolution strategy wiring (`first_write_wins`/`last_write_wins`/`prefer_success`) with deterministic conflict reject/replace test coverage.
- [x] P2-4 baseline completed: tenant-scoped BYOC cost/rejection instrumentation with optional limit-enforcement gate and runtime-control metrics for governance dashboards.
- [x] P2 expansion queue closed and handed off to next planning board: `docs/plans/backlog-reconciliation-v2-execution-board.md`.

### Backlog reconciliation v2 progress
- [x] P0-2 baseline completed: local data durability scripts (`backup`/`restore`/`validate`) plus Makefile wrappers and operator runbook procedure for deterministic local SQLite recovery drills.
- [x] P0-3 baseline completed: RC signoff evidence now includes local data-safety metadata and normalized parser output (`data_safety`) with advisory-by-default and opt-in required mode.
- [x] P1-1 baseline completed: BYOC governance metrics export contract added with tenant-scoped cost utilization, submission/rejection rates, and rejection reason rollup API response.
- [x] P1-2 baseline completed: tenant budget window policy added with deterministic window reset semantics, window-specific over-budget reason code, and governance export window metadata.
- [x] P1-3 baseline completed: RC signoff evidence now includes advisory governance alerts with thresholded utilization/rejection signals and normalized parser output (`governance_alerts`) for dashboard ingestion.
- [x] P2-1 baseline completed: sqlite-backed BYOC recovery chaos suite covers lease-expiry storms, restart-race parallel completion, replay collision pressure, and bulk conflict-strategy determinism.
- [x] P2-2 baseline completed: governance anomaly detector policy module added with deterministic threshold checks (utilization, rejection-rate, reason-dominance) and advisory findings included in governance metrics export.

---

## Platform Extensions — Slice 1 (Auth Hardening — branch: feature/slice1-auth-hardening)

### New contracts
- [x] `src/persistence/contracts.py` — `ApiKeyRecord` dataclass (stores SHA-256 hash, never plaintext)
- [x] `src/persistence/contracts.py` — `ApiKeyStore` ABC (`save_key`, `get_key`, `lookup_by_hash`, `delete_key`, `list_keys`)

### New SQLite adapter
- [x] `src/persistence/adapters/sqlite.py` — `SQLiteApiKeyStore` (upsert, lookup by hash, delete, list with optional tenant filter)

### Auth settings
- [x] `src/config/settings.py` — `AuthSettings` dataclass (`jwt_secret`, `jwks_url`, `algorithm`); added to `AppSettings.auth`

### JWT resolver
- [x] `src/identity/jwt_resolver.py` — `decode_jwt(token, secret, algorithm)` → `IdentityContext`; handles VALID, EXPIRED, and invalid tokens

### Auth middleware rewrite (async, multi-mode)
- [x] `src/api/middleware/auth.py` — `extract_identity` is now `async`; precedence: Bearer JWT → Bearer API-key → X-API-Key → X-Identity (test/dev only)
- [x] `src/api/dependencies.py` — `get_identity` awaits `extract_identity`; updated 401 message

### Key management router
- [x] `src/api/schemas/auth_schemas.py` — `ApiKeyCreateRequest/Response`, `ApiKeyInfo`, `ApiKeyListResponse`
- [x] `src/api/routers/admin_keys.py` — `POST /admin/keys`, `GET /admin/keys`, `DELETE /admin/keys/{key_id}`
- [x] `src/api/app.py` — includes `admin_keys` router

### Bootstrap wiring
- [x] `src/api/bootstrap.py` — creates `SQLiteApiKeyStore` from same `EXO_DB_PATH`; exposes `api_key_store` on `app.state` (None in memory mode)

### Tests
- [x] `tests/modules/api/test_auth_apikey.py` (12 tests — CRUD, auth, tenant filter, 503 without store, 401 without auth, prod environment blocks X-Identity)
- [x] `tests/modules/api/test_auth_jwt.py` (13 tests — decode unit tests + integration via TestClient)
- [x] Existing `test_slice1_transport.py` extract_identity tests updated for async call
- [x] Full test suite: **301 passed, 0 failed** (+25 new tests)

---

## Platform Extensions — Slice 0 (Persistent Storage — branch: feature/slice0-persistent-storage)

### New contracts
- [x] `src/persistence/contracts.py` — `PersistedToolRecord`, `PersistedAgentRecord` dataclasses
- [x] `src/persistence/contracts.py` — `ToolStore` ABC (`save_tool`, `delete_tool`, `list_tools`, `list_tenant_ids`)
- [x] `src/persistence/contracts.py` — `AgentStore` ABC (`save_agent`, `delete_agent`, `list_agents`, `list_tenant_ids`)

### New SQLite adapters
- [x] `src/persistence/adapters/sqlite.py` — `SQLiteToolStore` (upsert, delete, list, tenant isolation)
- [x] `src/persistence/adapters/sqlite.py` — `SQLiteAgentStore` (upsert, delete, list, tenant isolation)

### Bootstrap wiring
- [x] `src/api/bootstrap.py` — `persistence_backend` param (`"sqlite"` | `"memory"`); creates stores from `EXO_DB_PATH` env var (default `.exo_data/exo.db`)
- [x] `src/api/bootstrap.py` — exposes `tool_store`, `agent_store` on `app.state`; registers startup hydration hook
- [x] `src/runtime/tenant_runtime.py` — `TenantRuntimeFactory` accepts optional `session_store` param; falls back to `InMemorySessionStore` when None

### Startup hydration
- [x] `src/api/startup.py` — `hydrate_tenant_registries(app)` — loads persisted tools/agents into tenant registries on startup

### Router write-through
- [x] `src/api/routers/tools.py` — `register_tool` / `unregister_tool` write-through to `ToolStore` (no-op when None)
- [x] `src/api/routers/agents.py` — `register_agent` / `unregister_agent` write-through to `AgentStore` (no-op when None)

### Dependencies
- [x] `src/api/dependencies.py` — `get_tool_store()`, `get_agent_store()` — return store from `app.state` or `None`

### Tests
- [x] `tests/modules/persistence/test_tool_agent_stores.py` (16 tests — save, list, upsert, delete, tenant isolation, field roundtrip)
- [x] `tests/modules/api/test_persistence_roundtrip.py` (7 tests — tool/agent survive restart, delete persisted, tenant isolation, memory backend unaffected)
- [x] Full test suite: **276 passed, 0 failed** (+23 new tests)
