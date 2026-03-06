# eXo-brain

Provider-neutral AI orchestration platform with deterministic tool execution, multi-tenant runtime isolation, and a REST/SSE/WebSocket API for single-agent and multi-agent workloads.

## What this repository provides

- **API Platform** — FastAPI application with tenant-scoped tool/agent registration, SSE and WebSocket streaming, and live policy/quota management.
- **Provider-neutral runtime contracts** — `RuntimeAdapter` ABC with pluggable backends (OpenAI Agents SDK, custom adapters).
- **Deterministic-first tool execution** — every state-changing or high-impact tool call is routed through `DeterministicToolExecutor` and `PolicyMiddleware`.
- **Policy middleware** — auditable `before_tool_call` / `after_tool_call` decisions (`allow`, `deny`, `escalate`) with per-tenant overlay support.
- **Multi-tenant isolation** — `TenantRuntimeFactory` gives each tenant its own `ToolRegistry`, `AgentRegistry`, `PolicyMiddleware`, and session store.
- **MCP integration** — trust-tier and per-server health controls for MCP tool calls.
- **Background runtime** — task graph (DAG), scheduler, bounded worker pool, checkpoint/resume.

---

## Quick start

```bash
# 1. Create and activate a virtual environment
python -m venv .exo_env && source .exo_env/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Copy environment template and set your API key
cp .env.template .env
# Edit .env and set OPENAI_API_KEY=sk-...

# 4. Run tests
python -m pytest -q

# 5. Run architecture checks
python scripts/architecture/validate_layers.py
python scripts/architecture/scan_forbidden_imports.py

# 6. Start the API server
uvicorn src.api.app:create_app --factory --reload --port 8000
# API docs: http://localhost:8000/docs
```

---

## Project status (how it's going)

- **Purpose**: Build a provider-neutral AI orchestration platform where model providers are pluggable adapters and core orchestration remains deterministic, auditable, and tenant-isolated.
- **Current state**: Core bootstrap, API slices, and P2 expansion roadmap work are marked complete in the project checklist.
- **Progress tracking**:
  - `.cursor/research-for-refactor/12-bootstrap-checklist.md`
  - `docs/plans/p2-expansion-roadmap.md`
- **Operational health check**: run `python -m pytest -q`, `python scripts/architecture/validate_layers.py`, and `python scripts/architecture/scan_forbidden_imports.py`.

---

## Architecture principles

- Keep provider SDK code inside `src/runtime/*adapter*` modules only — never in core.
- Keep orchestration core provider-neutral — no branching on provider name.
- Route state-changing/high-impact tool operations through deterministic policy-governed execution.
- Preserve strict layer boundaries: `api → integration → core → runtime / tools / policies / persistence / observability`.
- Per-tenant isolation: each tenant's tools, agents, policies, and sessions are fully independent.

---

## Architecture

### Full layer map

```mermaid
flowchart TB
    subgraph api_layer [API Layer]
        CLI["HTTP Client / Browser / Notebook"]
        FAPI["FastAPI App\nsrc/api/app.py"]
        BOOT["Bootstrap\nsrc/api/bootstrap.py"]
        AUTH["Auth Middleware\nX-Identity header"]
        ROUTERS["Routers\ntools · agents · sessions · turns · providers · tenants"]
        SCHEMAS["Pydantic Schemas\nrequest / response / SSE+WS event envelope"]
    end

    subgraph tenant_layer [Tenant Runtime]
        TRF["TenantRuntimeFactory\nsrc/runtime/tenant_runtime.py"]
        TRC["TenantRuntimeContext\n(per tenant — isolated registries)"]
        TW["tool_wiring.py\nbuild_agent_tools() — late binding"]
    end

    subgraph integration [Integration Layer]
        HA["OrchestratorHostAdapter\nsubmit_turn()"]
    end

    subgraph core [Core Orchestration]
        ORCH["Orchestrator\nrun_turn()"]
        SC["SessionContext"]
        ER["EventRouter"]
        BR["BackgroundRuntime"]
        SCHED["TaskScheduler"]
        TG["TaskGraph (DAG)"]
        WP["WorkerPool"]
    end

    subgraph runtime [Runtime Adapters]
        RA["RuntimeAdapter (ABC)"]
        OAR["OpenAIAgentsRuntime\n(real SDK wiring)"]
        OCR["OpenAICompatibleRuntime"]
        CR["CustomRuntime"]
        MS["ModeSelector"]
        CM["CapabilityMap"]
    end

    subgraph tools [Tools Layer]
        TR["ToolRegistry\nlist_descriptors · unregister"]
        TE["DeterministicToolExecutor"]
        DEC["Decorators\nvalidation · authz · retry · audit · redaction"]
        PM["PluginManager"]
    end

    subgraph policies [Policies Layer]
        MW["DeterministicFirstPolicyMiddleware\nbefore_tool_call · after_tool_call"]
        RG["RiskGatePolicy"]
        POL["TenantPolicyOverlayStore\nper-tenant deny / escalate rules"]
    end

    subgraph agents [Agents Layer]
        AR["AgentRegistry\nrouting · handoff · fallback\nlist_routes · list_fallback_policies"]
    end

    subgraph mcp [MCP Layer]
        MTA["McpToolAdapter"]
        MR["McpRegistry\ntrust tiers · health"]
        CB["CircuitBreaker"]
        DLQ["DeadLetterQueue"]
    end

    subgraph persistence [Persistence]
        SS["InMemorySessionStore"]
        SQLITE["SQLiteAdapter"]
        POSTGRES["PostgresAdapter"]
    end

    subgraph observability [Observability]
        LOG["StructuredLogger"]
        TRACE["RuntimeTracer"]
        METRICS["RuntimeMetrics"]
        TL["RuntimeTimeline"]
    end

    subgraph identity_access [Identity + Access]
        IC["IdentityContext"]
        ACE["AccessPolicyEngine (RBAC)"]
    end

    subgraph tenancy [Tenancy]
        QM["TenantQuotaManager\nset_limit · check_submission"]
    end

    subgraph config [Config]
        SET["AppSettings"]
        PRR["ProviderRegistry\nget_adapter()"]
    end

    CLI --> FAPI
    FAPI --> AUTH
    FAPI --> BOOT
    BOOT --> TRF
    FAPI --> ROUTERS
    ROUTERS --> TRC
    TRC --> TR & AR & MW & QM & SS
    TRF --> TRC
    TRF --> HA
    TW --> OAR
    HA --> ORCH
    ORCH --> RA
    RA --> OAR & OCR & CR
    ORCH --> MS --> CM
    ORCH --> MW --> RG --> ACE
    ORCH --> TE --> TR & DEC & MW
    ORCH --> AR
    ORCH --> BR --> QM & SCHED
    SCHED --> TG & WP
    MTA --> MR & CB & DLQ & MW
    PRR --> RA
    SET --> PRR
```

---

### API request → tool execution flow

```mermaid
flowchart TD
    A["Client: POST /tenants/{id}/sessions/{id}/turns\n{input: 'What is 5 + 7?'}"] --> B["FastAPI Router\nresolve identity · get tenant context"]
    B --> C["TenantRuntimeFactory\nget_session_runtime(session_id)"]
    C --> D["OrchestratorHostAdapter.submit_turn()"]
    D --> E["Orchestrator.run_turn(session_id, user_input)"]
    E --> F["OpenAIAgentsRuntimeAdapter.run_turn()\nbuild_agent_tools() — late binding from ToolRegistry"]
    F --> G["Agent + Runner.run_streamed()\nOpenAI Agents SDK"]
    G --> H{SDK event?}
    H -->|text delta| I["RuntimeEvent.OUTPUT_DELTA\n→ SSE: output_delta"]
    H -->|tool call| J["FunctionTool.on_invoke_tool()\nroutes to DeterministicToolExecutor"]
    J --> K["PolicyMiddleware.before_tool_call()\nRiskGatePolicy + TenantPolicyOverlay"]
    K -->|DENY| L["TOOL_EXECUTION_ERROR returned to SDK"]
    K -->|ALLOW| M["handler(**args) — Python function executes"]
    M --> N["PolicyMiddleware.after_tool_call()\naudit · mode · payload checks"]
    N --> O["ToolResult returned to SDK\n→ SSE: tool_call + tool_result events"]
    O --> G
    H -->|run complete| P["RuntimeEvent.RUN_COMPLETE\n→ SSE: run_complete"]
```

---

### WebSocket multi-turn flow

```mermaid
flowchart TD
    A["WS /tenants/{id}/sessions/{id}/ws\n(persistent connection)"] --> B["Server: verify session exists"]
    B -->|unknown| C["Close 4404 — session not found"]
    B -->|ok| D["Hold OrchestratorHostAdapter for connection lifetime"]
    D --> E{Client message?}
    E -->|turn message| F["Create asyncio.Task\nstore run_id → task"]
    F --> G["submit_turn → stream events back over WS\noutput_delta · tool_call · tool_result · run_complete"]
    G --> E
    E -->|cancel message| H["task.cancel()\nemit run_cancelled event"]
    H --> E
    E -->|disconnect| I["Auto-cancel any in-flight task"]
```

---

### Background job execution flow

```mermaid
flowchart TD
    A["BackgroundRuntime.submit(job_id, TaskGraph, context)"] --> B["TenantQuotaManager\ncheck_submission() — hard or soft enforcement"]
    B -->|"quota exceeded + hard"| C["QuotaDecision: DENIED"]
    B -->|allowed| D["Create asyncio.Task\ntrack in job registry"]
    D --> E["TaskScheduler.execute(graph)"]
    E --> F["Identify ready wave\nTaskGraph.ready_nodes()"]
    F --> G["WorkerPool.run()\nbounded concurrency semaphore"]
    G --> H["_run_node() per node in parallel"]
    H --> I["CheckpointStore.get_checkpoint()\nresume from prior state if exists"]
    I --> J["Execute handler + RetryPolicy exponential backoff"]
    J -->|success| K["CheckpointStore.save_checkpoint()\nStructuredLogger · RuntimeTracer · RuntimeMetrics"]
    K --> L{All nodes done?}
    L -->|no| F
    L -->|yes| M["SchedulerResult → BackgroundRuntime"]
    J -->|"timeout / retries exhausted"| N["Mark node FAILED\ncancel downstream"]
```

---

### Policy and mode-selection decision tree

```mermaid
flowchart TD
    A["ToolCallContext arrives"] --> B{PolicyDecision\nnot ALLOW?}
    B -->|yes| C["DETERMINISTIC\npolicy blocks provider-native path"]
    B -->|no| D{Policy enforces\ndeterministic?}
    D -->|yes| C
    D -->|no| E{is_state_changing\nor HIGH / CRITICAL risk?}
    E -->|yes| C
    E -->|no| F{CapabilityMap\nreliability < 4 or missing function-calling?}
    F -->|yes| C
    F -->|no| G{Policy enforces\nspecific mode?}
    G -->|yes| H["Use policy-enforced mode"]
    G -->|no| I{Tool requests\nspecific mode?}
    I -->|yes| J["Use tool-requested mode"]
    I -->|no| K["PROVIDER_NATIVE (fast path)"]
```

---

### Key design principles

| Principle | Where enforced |
|---|---|
| Provider SDK never touches core | `RuntimeAdapter` ABC — adapters import SDK, orchestrator imports only ABC |
| Tool calls are intent, not execution | `FunctionTool.on_invoke_tool` delegates to `DeterministicToolExecutor` |
| State-changing ops are always deterministic | `ModeSelector` and `PolicyMiddleware` enforce unconditionally |
| Policy wraps every side-effect path | `before_tool_call` + `after_tool_call` on all execution paths |
| Per-tenant isolation | `TenantRuntimeFactory` — each tenant owns independent registries and session store |
| Policy changes are live | `TenantPolicyOverlayStore.set_overlay()` takes effect on the next tool call, no restart |
| Audit trail is tamper-evident | SHA-256 hash chain in `AuditChainRecord` |
| Secrets are never logged | `StructuredLogger._redact_context()` auto-redacts `secret/token/password/api_key` keys |
| Adapter plug-and-play | Implement 5-method `RuntimeAdapter` ABC → register in `ProviderRegistry` → selectable by `provider_id` |

---

## API endpoints (v1)

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Platform health check |
| `POST` | `/tenants/{id}/tools` | Register a tool (`handler_ref`, `description`, `parameters_schema`, risk tier) |
| `GET/DELETE` | `/tenants/{id}/tools[/{name}]` | List / get / delete tools |
| `POST` | `/tenants/{id}/agents` | Register agent (`instructions`, `capability_tags`, model metadata) |
| `GET/DELETE` | `/tenants/{id}/agents[/{agent_id}]` | List / get / delete agents |
| `POST/GET` | `/tenants/{id}/agents/routes` | Add / list handoff routes |
| `POST/GET` | `/tenants/{id}/agents/fallback` | Set / list fallback policies |
| `POST` | `/tenants/{id}/sessions` | Create a session (`agent_id`, `provider_id`) |
| `GET` | `/tenants/{id}/sessions/{session_id}` | Get session state |
| `POST` | `/tenants/{id}/sessions/{session_id}/turns` | Submit a turn — returns `text/event-stream` (SSE) |
| `WS` | `/tenants/{id}/sessions/{session_id}/ws` | WebSocket — persistent multi-turn with cancellation |
| `GET` | `/providers` | List all registered providers |
| `GET` | `/providers/{id}/health` | Provider health check |
| `GET` | `/providers/{id}/capabilities` | Provider capability map |
| `GET/PUT` | `/tenants/{id}/policy` | Read / apply tenant policy overlay |
| `GET/PUT` | `/tenants/{id}/quota` | Read / update tenant job quota |

---

## PR workflow

- Use PR-first delivery and branch-per-slice.
- Produce and keep `.local/review.md`, `.local/prep.md`, `.local/merge.md`.
- Merge only after tests and architecture checks pass:
  - `python -m pytest -q`
  - `python scripts/architecture/validate_layers.py`
  - `python scripts/architecture/scan_forbidden_imports.py`
