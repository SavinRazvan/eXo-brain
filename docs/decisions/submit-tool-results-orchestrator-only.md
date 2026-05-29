<!--
File: submit-tool-results-orchestrator-only.md
Path: docs/decisions/submit-tool-results-orchestrator-only.md
Role: ADR — continuation after tool execution stays in the orchestrator, not Agents SDK resume.
Used By:
 - docs/operations/adapter-installation.md
 - exo-adapter-openai operators
Depends On:
 - docs/plans/tenant-tool-execution-architecture.md
Notes:
 - Option (b) Agents resume in packaged adapter is deferred until a dedicated slice with tests.
-->

# Decision: `submit_tool_results` — orchestrator-only continuation

**Status:** Accepted for adapter **0.1.1+** (current lockstep **0.1.2**; updated 2026-05-29)

**Context:** The OpenAI Agents SDK supports resuming a run after local tool execution. eXo-brain routes state-changing tools through the deterministic tool executor and policy middleware; side effects stay in the control plane.

**Decision:**

1. **`planned_tool_call` / orchestrator `TOOL_INTENT`:** orchestrator executes tools, then calls `submit_tool_results`.
2. **`submit_tool_results` (OpenAI adapter, with `OPENAI_API_KEY` + registry + executor):** formats deterministic `ToolResult` payloads and runs a **continuation** via `Runner.run` so the user receives a final model answer (not only a count ack).
3. **Agents stream with delegating `FunctionTool`s:** tool calls run inside SDK tool bodies; the adapter does **not** re-emit `TOOL_INTENT` for stream `ToolCallItem` events (avoids double execution).

**Consequences:**

- In-SDK mid-stream resume of the *same* `run_streamed` handle is still not used; continuation is a fresh `Runner.run` with tool summaries.
- Governed `planned_tool_call` → execute → `submit_tool_results` → model answer is the supported multi-step contract.

**References:** [`tenant-tool-execution-architecture.md`](../plans/tenant-tool-execution-architecture.md), eXo_adapters `docs/packages-reference.md`.
