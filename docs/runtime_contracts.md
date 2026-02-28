# Runtime Contracts

## RuntimeAdapter
All runtime providers implement `RuntimeAdapter`:
- `start_session(session_id, metadata=None) -> SessionHandle`
- `run_turn(session_id, user_input, context) -> AsyncIterator[RuntimeEvent]`
- `submit_tool_results(session_id, run_id, tool_results) -> AsyncIterator[RuntimeEvent]`
- `get_capabilities() -> ProviderCapabilityMap`
- `healthcheck() -> HealthStatus`

## Core constraints
- Core orchestration consumes only runtime contract types.
- Runtime adapters normalize provider output into internal events.
- Runtime adapters do not own policy decisions.

## Mode selection
- `provider_native` for low-risk/read-only operations when capability + policy allow.
- `deterministic` required for state-changing/high-impact operations.

## Required event behavior
- Preserve correlation fields (`session_id`, `run_id`, `job_id`, `task_id`, `agent_id`, `provider_id`).
- Emit structured completion envelopes and normalized failure metadata.
