<!--
File: plugin_lifecycle.md
Path: docs/plugin_lifecycle.md
Role: Tool and agent plugin load/unload/reload contracts and safety rules.
Used By:
 - docs/README.md
 - docs/modules/tools.md
Depends On:
 - src/tools/plugins/plugin_manager.py
 - src/agents/plugin_manager.py
Notes:
 - Two parallel managers: tools vs agents. API registration uses HTTP routes, not these in-process plugin APIs, for most tenants.
 - Last reviewed: 2026-05-29
-->

# Plugin lifecycle

**Status:** active  
**Owner:** Savin I. Razvan

eXo-brain has **two** in-process plugin managers with the same lifecycle verbs but different registries:

| Manager | Path | Registers into |
|---|---|---|
| **Tool plugins** | `src/tools/plugins/plugin_manager.py` | `ToolRegistry` (`ToolPlugin` manifest + tool descriptors) |
| **Agent plugins** | `src/agents/plugin_manager.py` | `AgentRegistry` (agents, handoff routes, fallback policies) |

Customer-facing **tool/agent CRUD** uses HTTP APIs (`src/api/routers/tools.py`, `agents.py`) and persistence — not necessarily these plugin classes. Use this doc when packaging **bundled** tool or agent extensions inside a deployment or test harness.

## Supported lifecycle operations

Both managers implement:

- `load_plugin`
- `unload_plugin`
- `reload_plugin`
- `validate_compatibility`
- `list_plugins`

**Agent-only:** `list_lifecycle_audit_records()` on `AgentPluginManager` (in-memory lifecycle audit trail).

## Safety requirements

- **Unload guard:** `unload_plugin(..., has_active_non_idempotent_tasks=True)` raises if non-idempotent work is still active (both managers).
- **Compatibility:** `validate_compatibility` checks `compatible_core_major` on the plugin manifest against the manager’s `core_major_version`.
- **Agent reload:** on failure, `reload_plugin` restores the previous plugin instance when possible.
- **Agent authorization:** optional `LifecyclePolicy` can deny load/unload/reload (`AgentPluginManager._authorize`).
- Tool/agent **decorator ordering** for security hooks is enforced in the tool execution path ([modules/tools.md](modules/tools.md)); plugins must not bypass policy middleware.

## Extension model

- **Tool plugins** contribute `ToolDescriptor`s to the tenant tool registry.
- **Agent plugins** contribute agent specs, routes, and fallback policies.
- Core orchestration stays decoupled from plugin internals; plugins mutate registries, not `Orchestrator` directly.

## Tests (anchors)

- `tests/modules/agents/test_agent_plugins.py`
- Tool plugin behavior covered via registry/executor tests under `tests/modules/tools/`

## Related

- [mcp_integration.md](mcp_integration.md) — MCP servers are a separate boundary from tool/agent plugins
- [customer-api-integration-guide.md](api/customer-api-integration-guide.md) §6–§7 — HTTP tool/agent lifecycle
