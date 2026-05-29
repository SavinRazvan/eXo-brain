<!--
File: mcp_integration.md
Path: docs/mcp_integration.md
Role: MCP module boundaries, trust/health controls, and execution safety contracts.
Used By:
 - docs/README.md
 - docs/modules/README.md
 - docs/roadmap/enterprise-module-hardening-integration-plan.md
Depends On:
 - src/mcp/
 - tests/modules/mcp/
Notes:
 - MCP adapter is implemented and tested; default customer HTTP turn path uses tenant tools/BYOC/sandbox unless explicitly wired to MCP.
 - Last reviewed: 2026-05-29
-->

# MCP integration

**Status:** active (module boundary)  
**Owner:** Savin I. Razvan

## Module boundary

`src/mcp/` isolates Model Context Protocol integrations from orchestration core:

| File | Role |
|---|---|
| `mcp_registry.py` | Server registry, trust tiers, health state |
| `mcp_client_adapter.py` | Client protocol seam (in-process stub + `network_mcp_client_adapter.py` for network) |
| `mcp_tool_adapter.py` | Policy-gated tool execution, circuit breaker, DLQ, compensation hooks |

Layer placement: [architecture/mvp.md](architecture/mvp.md) (`mcp` layer). Hardening track: [enterprise-module-hardening-integration-plan.md](roadmap/enterprise-module-hardening-integration-plan.md) Phase 2.

## Trust and health

**Trust tiers** (`McpTrustTier`): `trusted`, `restricted`, `sandboxed`.

**Health states** (`McpHealthState`): `healthy`, `degraded`, `unavailable`.

`McpRegistry.get_server()` blocks disabled or `unavailable` servers before execution. `McpToolAdapter.sync_server_health()` updates health before calls (see tests).

State-changing or high-impact work on **restricted** tiers is blocked by default in `McpToolAdapter` (policy + tier checks).

## Execution path

1. `McpToolAdapter.execute(server_id, tool_name, context)` runs `policy.before_tool_call`.
2. Non-`allow` → deterministic blocked `ToolResult` with reason metadata (no raw exception leak).
3. Circuit breaker, bounded retry/timeout, optional DLQ on failure paths.
4. `policy.after_tool_call` on success paths.

Uses the same `ToolResult` / `PolicyAction` envelopes as the deterministic tool runtime ([modules/tools.md](modules/tools.md)).

## Integration status (factual)

| Area | Status |
|---|---|
| Module + unit tests | **Shipped** — `tests/modules/mcp/` |
| Default API turn / orchestrator wiring | **Not on the main customer path** — production turns use registered tenant tools, sandbox, and BYOC unless you compose `McpToolAdapter` into your deployment integration |
| Roadmap | Phase 2 hardening in [module hardening plan](roadmap/enterprise-module-hardening-integration-plan.md) |

When wiring MCP into a host path, preserve ingress + tool policy ordering from [governed-execution-pipeline.md](architecture/governed-execution-pipeline.md).

## Required behavior

- MCP tool calls are policy-gated (`DeterministicFirstPolicyMiddleware` or equivalent).
- Unavailable servers are blocked with auditable reason codes.
- Timeout, retry, circuit breaker, and DLQ behavior are bounded and explicit (`src/resilience/*`).
- Structured logs use `mcp.*` event names; failures map to `ToolStatus` envelopes.

## Tests (anchors)

- `tests/modules/mcp/test_mcp_registry.py`
- `tests/modules/mcp/test_mcp_tool_adapter.py`

## Related

- [plugin_lifecycle.md](plugin_lifecycle.md) — separate extension model for tool/agent plugins
- [runtime_contracts.md](runtime_contracts.md) — provider adapter boundary (not MCP)
