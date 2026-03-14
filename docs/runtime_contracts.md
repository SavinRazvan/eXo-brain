# Runtime Contracts

## RuntimeAdapter (southbound provider boundary)

All runtime providers implement `RuntimeAdapter`:
- `start_session(session_id, metadata=None) -> SessionHandle`
- `run_turn(session_id, user_input, context) -> AsyncIterator[RuntimeEvent]`
- `submit_tool_results(session_id, run_id, tool_results) -> AsyncIterator[RuntimeEvent]`
- `get_capabilities() -> ProviderCapabilityMap`
- `healthcheck() -> HealthStatus`

`RuntimeAdapter` is an internal provider-facing contract. It standardizes how orchestration talks to providers and provider SDKs.

## Northbound vs southbound boundary

- Southbound (provider boundary): runtime adapters in `src/runtime/*`.
- Northbound (client boundary): external HTTP/WebSocket API surfaces in `src/api/*`.
- A provider can be "OpenAI-compatible" southbound without exposing a public OpenAI-compatible northbound API.
- Public `/v1/chat/completions` parity is an API gateway concern, not an adapter contract by itself.

## Interaction mode ownership

| Interaction mode | Primary owner | Expected runtime responsibility |
|---|---|---|
| `chat` (OpenAI-compatible chat/completions style) | API gateway + runtime adapter | Execute model turns and normalize responses/events |
| `agents` (Agents SDK style) | Runtime adapter | Run agent-native interactions and emit tool intent/output events |
| `workflow` (multi-step orchestration) | `core` orchestration layer | Coordinate state graph/steps; runtime only executes model/tool turns |

Workflow behavior should stay in orchestration (`src/core/*`) so provider adapters remain replaceable and testable.

## Core constraints

- Core orchestration consumes only runtime contract types.
- Runtime adapters normalize provider output into internal events.
- Runtime adapters do not own policy decisions.
- Policy middleware wraps all state-changing tool paths regardless of runtime interaction mode.

## Mode selection

- `provider_native` for low-risk/read-only operations when capability + policy allow.
- `deterministic` required for state-changing/high-impact operations.
- Capability uncertainty must fall back to deterministic mode.

## Required event behavior

- Preserve correlation fields (`session_id`, `run_id`, `job_id`, `task_id`, `agent_id`, `provider_id`).
- Emit structured completion envelopes and normalized failure metadata.
- Keep envelope shape stable across `chat`, `agents`, and `workflow` entry paths.
