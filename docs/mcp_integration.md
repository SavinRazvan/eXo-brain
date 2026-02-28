# MCP Integration

## Module boundary
`src/mcp` isolates MCP integrations from core orchestration:
- `mcp_registry.py`
- `mcp_client_adapter.py`
- `mcp_tool_adapter.py`

## Current controls
- Trust tiers (`trusted`, `restricted`, `sandboxed`).
- Per-server health state tracking (`healthy`, `degraded`, `unavailable`).
- Health sync before execution.
- Structured deterministic envelope on validation/policy failures.

## Required behavior
- MCP tool calls are policy-gated.
- Unavailable servers are blocked with auditable reason codes.
- Timeout and retry policy are bounded and explicit.
