# eXo-brain

Provider-neutral orchestration framework for deterministic tool execution, multi-adapter runtime flows, and background multi-agent workloads.

## What this repository provides
- Provider-neutral runtime contracts and adapter boundary.
- Deterministic-first tool execution for state-changing/high-impact operations.
- Policy middleware with auditable decisions (`allow`, `deny`, `escalate`).
- MCP integration boundary with trust-tier and per-server health controls.
- Background runtime primitives (task graph, scheduler, worker pool, checkpoint/resume).

## Quick start
1. Create a Python virtual environment and install project dependencies.
2. Copy `.env.template` to `.env` and set required values.
3. Run tests:
   - `python -m pytest -q`
4. Run architecture checks:
   - `python scripts/architecture/validate_layers.py`
   - `python scripts/architecture/scan_forbidden_imports.py`

## Architecture principles
- Keep provider SDK specifics inside `src/runtime/*adapter*` modules.
- Keep orchestration core provider-neutral.
- Route state-changing/high-impact tool operations through deterministic policy-governed execution.
- Preserve strict layer boundaries (`integration -> core -> runtime/tools/policies/persistence/observability`).

## Architecture

### Layer map

```mermaid
flowchart TB
    subgraph external [External Callers]
        HOST["Host / API / CLI"]
    end

    subgraph integration [Integration Layer]
        HA["HostAdapter\nOrchestratorHostAdapter"]
    end

    subgraph core [Core Orchestration]
        ORCH["Orchestrator\nrun_turn()"]
        SC["SessionContext"]
        ER["EventRouter"]
        BR["BackgroundRuntime"]
        SCHED["TaskScheduler"]
        TG["TaskGraph (DAG)"]
        WP["WorkerPool"]
        WL["WorkflowLoader"]
    end

    subgraph runtime [Runtime Adapters]
        RA["RuntimeAdapter (ABC)"]
        OAR["OpenAIAgentsRuntime"]
        OCR["OpenAICompatibleRuntime"]
        CR["CustomRuntime"]
        MS["ModeSelector"]
        CM["CapabilityMap"]
    end

    subgraph tools [Tools Layer]
        TR["ToolRegistry"]
        TE["DeterministicToolExecutor"]
        DEC["Decorators\nvalidation · authz · retry · audit · redaction"]
        PM["PluginManager"]
    end

    subgraph policies [Policies Layer]
        MW["PolicyMiddleware\nDeterministicFirstPolicyMiddleware"]
        RG["RiskGatePolicy\nbefore_tool_call · after_tool_call"]
        RR["ReleaseGuardrails\ncan_release()"]
    end

    subgraph agents [Agents Layer]
        AR["AgentRegistry\nrouting · handoff · fallback"]
        APM["AgentPluginManager\nlifecycle audit"]
    end

    subgraph mcp [MCP Layer]
        MTA["McpToolAdapter\nexecute()"]
        MR["McpRegistry\ntrust tiers · health"]
        CB["CircuitBreaker"]
        DLQ["DeadLetterQueue"]
        CH["CompensationHooks"]
    end

    subgraph persistence [Persistence Layer]
        PC["Contracts ABC\nSessionStore · CheckpointStore\nEventStore · AuditStore · WorkflowStore"]
        SQLITE["SQLiteAdapter"]
        POSTGRES["PostgresAdapter"]
        FACTORY["PersistenceBundle\nbuild_default_persistence_bundle()"]
    end

    subgraph resilience [Resilience Layer]
        RP["RetryPolicy\nexponential backoff"]
        CB2["CircuitBreaker"]
        DLQ2["DLQ"]
        COMPH["CompensationHooks"]
    end

    subgraph observability [Observability Layer]
        LOG["StructuredLogger\ncorrelation_id · redaction"]
        TRACE["RuntimeTracer\nspan lifecycle"]
        METRICS["RuntimeMetrics\ncounters · latency · gauges"]
        TL["RuntimeTimeline\nappend-only"]
        GATE["GateEvaluator\nSLO thresholds"]
    end

    subgraph identity_access [Identity + Access Control]
        IC["IdentityContext\nActorType · TokenValidationState"]
        IRE["resolve_identity()"]
        ACE["AccessPolicyEngine\nRBAC · audit-only mode"]
        RBAC["aggregate_permissions()"]
    end

    subgraph tenancy_secrets [Tenancy + Secrets]
        TC["TenantContext"]
        QM["TenantQuotaManager"]
        POL["TenantPolicyOverlayStore"]
        SP["SecretsProvider\nEnv · Cached · rotation hook"]
    end

    subgraph audit_compliance [Audit + Compliance]
        AT["AuditChainRecord\nSHA-256 hash chain"]
        EB["EvidenceBundle\nbuild_evidence_bundle()"]
    end

    subgraph config [Config Layer]
        SET["AppSettings\nall runtime defaults"]
        PRR["ProviderRegistry\nstartup validation · healthcheck · fallback"]
    end

    HOST --> HA
    HA --> ORCH
    ORCH --> SC
    ORCH --> ER
    ORCH --> RA
    RA --> OAR & OCR & CR
    ORCH --> MS
    MS --> CM
    ORCH --> MW
    MW --> RG
    RG --> ACE
    ORCH --> TE
    TE --> TR
    TE --> DEC
    TE --> MW
    ORCH --> AR
    ORCH --> BR
    BR --> QM
    BR --> SCHED
    SCHED --> TG
    SCHED --> WP
    SCHED --> RP
    SCHED --> PC
    MTA --> MR
    MTA --> CB
    MTA --> DLQ
    MTA --> CH
    MTA --> MW
    PC --> SQLITE & POSTGRES & FACTORY
    SET --> PRR
    PRR --> RA
    PRR --> SP
```

---

### Single-turn execution flow

```mermaid
flowchart TD
    A["Host submits turn\nHostAdapter.submit_turn()"] --> B["OrchestratorHostAdapter\nextracts session fields → context dict"]
    B --> C["Orchestrator.run_turn(turn, context)"]
    C --> D["Build SessionContext\nresolve_identity() → IdentityContext"]
    D --> E["RuntimeAdapter.start_session()\nreturns SessionHandle"]
    E --> F["RuntimeAdapter.run_turn()\nyields RuntimeEvents async"]

    F --> G{Event type?}

    G -->|OUTPUT_DELTA| H["Stream text delta\nto host caller"]
    G -->|RUN_COMPLETE| I["Yield final event\nend of stream"]
    G -->|TOOL_INTENT| J["PolicyMiddleware.before_tool_call()\nRiskGatePolicy.evaluate()"]

    J --> K{PolicyDecision?}

    K -->|DENY| L["blocked_result()\nreturn policy envelope\nno side effects"]
    K -->|ESCALATE| L

    K -->|ALLOW| M["ModeSelector\nselect_execution_mode()"]

    M --> N{CapabilityMap\n+ policy flags?}

    N -->|"state-changing\nHIGH/CRITICAL risk\nor caps uncertain"| O["DETERMINISTIC mode"]
    N -->|"low-risk · provider\ncapable · policy pass"| P["PROVIDER_NATIVE mode"]

    O --> Q["DeterministicToolExecutor.execute()"]
    Q --> Q1["Validate ToolCallContext schema"]
    Q1 --> Q2["Apply decorators stack\nvalidation → authz → retry → audit → redaction"]
    Q2 --> Q3["Resolve handler from ToolRegistry\ncall handler()"]
    Q3 --> Q4["PolicyMiddleware.after_tool_call()\ncorrelation_id · mode · payload checks"]
    Q4 --> Q5["ToolResult envelope\nwith ExecutionMetadata + PolicyAudit"]

    P --> R["RuntimeAdapter.submit_tool_results()\nprovider-native path"]
    R --> F

    Q5 --> S["Resume run_turn stream"]
    S --> F
```

---

### Background job execution flow

```mermaid
flowchart TD
    A["BackgroundRuntime.submit(job_id, TaskGraph, context)"] --> B["TenantQuotaManager\ncheck_submission()\nhard or soft enforcement"]
    B -->|"quota exceeded + hard"| C["QuotaDecision: DENIED\nreturn error, no job created"]
    B -->|allowed| D["Create asyncio.Task\ntrack in job registry"]
    D --> E["TaskScheduler.execute(graph)"]

    E --> F["Identify ready wave\nTaskGraph.ready_nodes()\nno unmet dependencies"]
    F --> G["WorkerPool.run()\nbounded concurrency semaphore"]
    G --> H["For each node in parallel\n_run_node()"]

    H --> I["CheckpointStore.get_checkpoint()\nresume from prior state if exists"]
    I --> J["Execute node handler\nwith retry loop\nRetryPolicy exponential backoff"]

    J -->|success| K["CheckpointStore.save_checkpoint()\nmark node COMPLETED"]
    K --> L["Structured log + span + metrics\nStructuredLogger · RuntimeTracer · RuntimeMetrics"]
    L --> M{All nodes done?}
    M -->|no| F
    M -->|yes| N["SchedulerResult\nreturn to BackgroundRuntime"]

    J -->|"timeout / error exhausted"| O["Mark node FAILED\ncancel downstream nodes"]
    O --> P["BackgroundRuntime updates JobStatus\njob available for cancel/resume"]
```

---

### MCP tool execution flow

```mermaid
flowchart TD
    A["McpToolAdapter.execute(call_context)"] --> B["PolicyMiddleware.before_tool_call()\nRiskGatePolicy check"]
    B -->|DENY| C["blocked_result() — return immediately"]
    B -->|ALLOW| D["CircuitBreaker.allow(server_id)\nfailure threshold check"]
    D -->|tripped| E["blocked_result() — circuit open"]
    D -->|allowed| F["_sync_server_health()\nMcpRegistry health state sync"]
    F --> G["_enforce_trust_tier()\nTRUSTED: unrestricted\nRESTRICTED: block state-changing\nSANDBOXED: block HIGH/CRITICAL or state-changing"]
    G -->|"blocked by tier"| H["blocked_result() — trust violation"]
    G -->|allowed| I["Retry loop\nasyncio.wait_for timeout per attempt"]
    I -->|success| J["CircuitBreaker.record_success()\nPolicyMiddleware.after_tool_call()"]
    J --> K["ToolResult with MCP metadata\nserver_id · trust_tier · attempt count"]
    I -->|"TimeoutError, retries remaining"| L["increment attempt\nretry"]
    L --> I
    I -->|"TimeoutError, retries exhausted"| M["DeadLetterQueue.push()\nCorrelationId + reason_code + payload"]
    M --> N["CompensationHooks.run(reason_code)\nbest-effort side-effect recovery"]
    N --> O["ToolResult with TIMEOUT_EXHAUSTED error"]
    I -->|"other exception"| P["CircuitBreaker records failure\nToolResult with error envelope"]
```

---

### Policy and mode-selection decision tree

```mermaid
flowchart TD
    A["ToolCallContext arrives\nat ModeSelector"] --> B{PolicyDecision\nnot ALLOW?}
    B -->|yes| C["DETERMINISTIC\npolicy blocks provider-native path"]
    B -->|no| D{Policy enforces\ndeterministic?}
    D -->|yes| C
    D -->|no| E{is_state_changing\nor HIGH / CRITICAL risk?}
    E -->|yes| C
    E -->|no| F{CapabilityMap\nreliability score < 4\nor missing function-calling?}
    F -->|yes| C
    F -->|no| G{Policy enforces\nspecific mode?}
    G -->|yes| H["Use policy-enforced mode"]
    G -->|no| I{Tool requests\nspecific mode?}
    I -->|yes| J["Use tool-requested mode"]
    I -->|no| K["PROVIDER_NATIVE\n(fast path)"]
```

---

### Key design principles

| Principle | Where enforced |
|---|---|
| Provider SDK never touches core | `RuntimeAdapter` ABC — adapters import SDK, orchestrator imports only ABC |
| Tool calls are intent, not execution | `TOOL_INTENT` event → orchestrator decides execution path |
| State-changing ops are always deterministic | `ModeSelector` hardcodes this unconditionally |
| Policy wraps every side-effect path | `PolicyMiddleware.before_tool_call` + `after_tool_call` on all three paths |
| Tenant isolation fails closed | `PersistenceIsolationError` raised on any cross-tenant read |
| Audit trail is tamper-evident | SHA-256 hash chain in `AuditChainRecord` |
| Release gates fail closed | `can_release()` returns `False` if evidence is absent |
| Secrets are never logged | `StructuredLogger._redact_context()` auto-redacts `secret/token/password/api_key` keys |

---

## PR workflow
- Use PR-first delivery and branch-per-slice.
- Produce and keep `.local/review.md`, `.local/prep.md`, `.local/merge.md`.
- Merge only after tests and architecture checks pass.
