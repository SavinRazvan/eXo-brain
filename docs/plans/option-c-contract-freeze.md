# Option C Contract Freeze Matrix

## Status

- Date: 2026-03-11
- Scope: Slice A (`runbook-sliceA`)
- Mode: API-first, no mandatory UI dependency

## Contract Boundaries

| Plane | Contract | File | Stability |
|---|---|---|---|
| Control -> Adapter | `RuntimeAdapter` | `src/runtime/runtime_adapter.py` | Frozen (`v1`) |
| Control -> Data | `ToolExecutionAdapter` | `src/tools/execution_adapter.py` | Frozen (`v1`) |
| Policy/Execution Envelope | `ToolCallContext`, `PolicyDecision`, `ToolResult` | `src/schemas/tool_io.py` | Frozen (`v1`) |
| Runtime Event Stream | `RuntimeEvent` + turn envelope | `src/schemas/events.py`, `src/api/schemas/turn_schemas.py` | Frozen (`v1`) |

## Frozen Interface Matrix

### `RuntimeAdapter` (`src/runtime/runtime_adapter.py`)

Required methods:

- `start_session(session_id, metadata) -> SessionHandle`
- `run_turn(session_id, user_input, context) -> AsyncIterator[RuntimeEvent]`
- `submit_tool_results(session_id, run_id, tool_results) -> AsyncIterator[RuntimeEvent]`
- `get_capabilities() -> ProviderCapabilityMap`
- `healthcheck() -> HealthStatus`

Compatibility rules:

1. Method names and argument names are frozen for `v1`.
2. Return envelopes must stay provider-neutral.
3. Provider SDK types must not leak through this interface.

### `ToolExecutionAdapter` (`src/tools/execution_adapter.py`)

Required methods:

- `backend_id: str` (property)
- `execute(call, descriptor) -> ToolResult`

Optional methods:

- `request_cancellation(call_id) -> bool`
- `control_stats() -> dict[str, int]`
- `cleanup_events(limit) -> list[dict[str, str]]`
- `drain_progress_events(call_id) -> list[dict[str, str]]`

Compatibility rules:

1. `execute()` must return normalized `ToolResult` with valid `ToolStatus`.
2. Adapters may be sync internally, but must honor timeout and cancellation contracts.
3. Optional hooks must degrade safely (default no-op behavior).

### Tool IO Envelope (`src/schemas/tool_io.py`)

Frozen core fields:

- `ToolCallContext`: `schema_version`, IDs, tenant/identity scope, `tool_name`, `arguments`, risk/mode flags
- `PolicyDecision`: `decision`, `reason_code`, optional enforced mode/audit
- `ToolResult`: `status`, `result` or `error`, execution metadata, audit trail

Compatibility rules:

1. Envelope schema must be backward-compatible (append-only for new fields).
2. `schema_version` must increment on any non-backward-compatible change.
3. `ToolStatus` values are contract-level and must not be repurposed.

## Adapter Packaging Contract

Target package split:

1. `exo-brain-core-contracts`
   - ships dataclass/schema contracts and enums only
2. `exo-brain-adapter-sdk`
   - helper base classes + contract validation harness
3. `exo-adapter-<provider>`
   - provider-specific runtime implementations

Provider package minimum requirements:

- Implement full `RuntimeAdapter` contract.
- Pass adapter conformance suite.
- Expose stable entrypoint for dynamic loading.
- Publish capability map and healthcheck behavior.

## Conformance Checklist

Each adapter package must prove:

1. Session lifecycle compatibility (`start_session` + metadata).
2. Turn streaming compatibility (`run_turn` event sequence correctness).
3. Tool result continuation compatibility (`submit_tool_results` path).
4. Capability declaration correctness (`get_capabilities` fields complete).
5. Healthcheck safety (deterministic healthy/degraded/down mapping).
6. No provider-specific types crossing core boundaries.
7. Policy and deterministic tool execution contracts remain enforceable.

## Change Control

- Any `v1` contract-breaking change requires:
  1. RFC in `docs/plans/`
  2. compatibility impact report
  3. migration strategy and timeline
  4. new schema version (`v2+`)

- Until `v2` is accepted, Option C implementation must remain within this `v1` freeze.

