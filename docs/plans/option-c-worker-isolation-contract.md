# Option C Worker Isolation Contract

## Status

- Date: 2026-03-11
- Scope: Slice C (`runbook-sliceC`)
- Applies to: hosted sandbox runtime + BYOC pull-worker runtime

## Contract Goal

Guarantee that tool execution workers remain isolated, cancellable, and bounded, while
the control plane keeps deterministic policy ownership.

## Isolation Boundaries

### Control plane responsibilities

- Validate tool intent (`ToolCallContext`) and enforce policy gates.
- Choose execution adapter.
- Emit canonical runtime events and audit metadata.
- Reject requests when tenant admission controls are exceeded.

### Data plane responsibilities

- Execute approved jobs only.
- Respect timeout and cancellation contracts.
- Return normalized `ToolResult`/BYOC result envelopes.
- Never bypass policy or tenant scoping constraints.

## Runtime Contract (hosted + BYOC)

### Required guarantees

1. **Tenant isolation**: no cross-tenant job claim/result visibility.
2. **Timeout enforcement**: each job must terminate or be marked timeout within configured `timeout_ms`.
3. **Cancellation propagation**: cancellation requested by run control must forward to adapter runtime.
4. **Idempotent result ingestion** (BYOC): duplicate submit payloads must not mutate state twice.
5. **Lease safety** (BYOC): expired leases are requeued or moved to DLQ according to claim policy.
6. **Deterministic envelope**: terminal outcomes map to stable `ToolStatus`.

### Health and lifecycle model

- Healthy: adapter can accept/execute claims.
- Degraded: adapter remains available but emits operational warnings (for example saturation, elevated timeout).
- Unhealthy: adapter rejects admission; control plane surfaces rejection to API clients.

## Existing code mapping

- BYOC connector runtime: `src/tools/byoc/connector_runtime.py`
- BYOC envelope contracts: `src/tools/byoc/job_contracts.py`
- Hosted sandbox runtime: `src/tools/sandbox/runtime.py`
- Execution abstraction: `src/tools/execution_adapter.py`
- Cancellation + run control APIs: `src/api/routers/runtime_control.py`, `src/api/routers/turns.py`

## Validation Checklist

- Cancellation path:
  - `turns` endpoint marks run cancellation and forwards call IDs to execution adapter.
- Timeout path:
  - adapter returns timeout result with normalized status and error code.
- Lease/claim path (BYOC):
  - claim uses tenant + lease token.
  - stale lease requeue and claim-attempt protections remain active.
- Ingestion path:
  - submit result enforces worker token validation + idempotency key behavior.

## Rollback Conditions

Rollback or block promotion if any are observed:

- cross-tenant result visibility
- non-terminal hanging runs after timeout budget
- duplicate BYOC submit mutating terminal state
- cancellation request does not propagate to execution backend

