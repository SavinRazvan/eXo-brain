# MVP Architecture

## Layers
- `integration`: host boundary; no orchestration or policy ownership.
- `core`: orchestration, background execution, workflow/session lifecycle.
- `runtime`: provider/runtime adapters implementing the internal runtime contract.
- `tools`: deterministic execution runtime and tool registry/decorator chain.
- `mcp`: MCP server/client/tool boundary with trust and health controls.
- `policies`: policy middleware and risk/access decisions.
- `persistence`: durable state interfaces and storage adapters.
- `observability`: logs, metrics, traces, and timeline reconstruction.
- `schemas`: typed contracts and envelopes used across layers.

## High-level flow
1. Host submits a turn via `integration`.
2. `core.orchestrator` selects execution mode with policy + capability checks.
3. Runtime emits tool intent events or output events.
4. Tool intents execute through deterministic runtime and policy gates.
5. Tool results are returned via normalized envelopes.
6. Observability modules emit correlation-rich execution telemetry.

## Guardrails
- No provider SDK imports in orchestration core.
- No bypass for state-changing/high-impact tool paths.
- Policy decisions must carry auditable reason codes.
- Runtime adapter outputs must remain internal schema-compliant events.
