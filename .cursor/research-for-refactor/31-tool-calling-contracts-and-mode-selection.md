# Tool Calling Contracts and Mode Selection

## Goal
Define production-ready contract shapes for hybrid tool execution so provider adapters remain swappable and high-risk side effects stay deterministic.

## Core Principle
- Models emit tool intent.
- Framework policy decides if execution is allowed.
- Deterministic tool runtime executes side effects when risk/policy/capability requires it.

## Canonical Schemas (V1)

### `ToolCallContext`
```yaml
schema_version: "1.0"
call_id: "tc_123"
session_id: "sess_123"
run_id: "run_123"
job_id: "job_123"
task_id: "task_123"
agent_id: "agent_planner"
provider_id: "openai"
tool_name: "sheet_operations"
arguments: { "operation": "append_row", "sheet_id": "abc" }
risk_tier: "high"   # low|medium|high|critical
is_state_changing: true
requested_mode: "provider_native"   # provider_native|deterministic|auto
timestamp_utc: "2026-02-28T00:00:00Z"
```

### `PolicyDecision`
```yaml
schema_version: "1.0"
decision: "allow"   # allow|deny|escalate
reason_code: "RISK_WRITE_REQUIRES_DETERMINISTIC"
message: "State-changing tools require deterministic runtime."
enforced_mode: "deterministic"   # optional
review_required: false
review_channel: null
audit:
  policy_id: "policy-risk-gate-v1"
  policy_version: "1.0.0"
  correlation_id: "corr_123"
```

### `ToolResult`
```yaml
schema_version: "1.0"
call_id: "tc_123"
tool_name: "sheet_operations"
status: "success"   # success|error|blocked|timeout|cancelled
result: { "rows_written": 1 }
error:
  code: null
  category: null
  message: null
  retryable: false
  details: null
execution:
  mode_used: "deterministic"   # provider_native|deterministic
  started_at_utc: "2026-02-28T00:00:01Z"
  finished_at_utc: "2026-02-28T00:00:02Z"
  duration_ms: 1045
  attempt: 1
  timeout_ms: 30000
audit:
  correlation_id: "corr_123"
  decision_reason_code: "RISK_WRITE_REQUIRES_DETERMINISTIC"
```

### `ProviderCapabilityMap`
```yaml
provider_id: "openai"
supports_agents_sdk_native: true
supports_openai_compatible_api: false
supports_streaming: true
supports_function_calling: true
supports_structured_output: true
supports_handoffs: true
max_context_tokens: 128000
reliability_score: 5
security_tier: "managed_vendor"   # managed_vendor|self_managed|local_only
recommended_runtime_mode: "hybrid"   # provider_native|deterministic|hybrid
```

## Runtime Adapter Contract (Required)
- `start_session(session_id: str, metadata: dict | None = None) -> SessionHandle`
- `run_turn(session_id: str, user_input: str, context: dict) -> AsyncIterator[RuntimeEvent]`
- `submit_tool_results(session_id: str, run_id: str, tool_results: list[ToolResult]) -> AsyncIterator[RuntimeEvent]`
- `get_capabilities() -> ProviderCapabilityMap`
- `healthcheck() -> HealthStatus`

## Mode Selection Rules (Deterministic-First Safety)
1. If `is_state_changing == true`, enforce deterministic mode.
2. If `risk_tier in {high, critical}`, enforce deterministic mode.
3. If provider capability is partial/unknown for required features, enforce deterministic mode.
4. If policy decision is `deny`, do not execute tool; emit `status=blocked`.
5. Use provider-native mode only when risk is low/read-only and policy + capability checks pass.

## Required Logs and Traces
- Required IDs: `job_id`, `task_id`, `session_id`, `run_id`, `agent_id`, `call_id`, `provider_id`, `correlation_id`.
- Required decision fields: `decision`, `reason_code`, `mode_used`, `attempt`, `duration_ms`.
- Every failed or blocked call must include normalized error/audit envelope.

## Test Requirements (V1)
- Unit: selector rules, policy decisions, envelope validation.
- Integration: one full turn with deterministic tool call and `submit_tool_results`.
- Security: blocked high-risk tool call emits auditable `blocked` result.
- Portability: same workflow contract passes on OpenAI adapter and one non-OpenAI/mock adapter.
- Replay: deterministic run can be replayed with equivalent tool side-effect path.

## Related Docs
- `02-target-architecture.md`
- `03-tool-calling-decision.md`
- `08-module-requirements-matrix.md`
- `10-provider-capability-matrix.md`
- `22-interface-contract-template.md`
