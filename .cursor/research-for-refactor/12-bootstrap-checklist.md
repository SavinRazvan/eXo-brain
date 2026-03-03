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
