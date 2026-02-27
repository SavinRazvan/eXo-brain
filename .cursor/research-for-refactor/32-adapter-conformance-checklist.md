# Adapter Conformance Checklist

## Goal
Define a pass/fail checklist every provider adapter must satisfy before being enabled in production profiles.

## Scope
Applies to all runtime adapters:
- OpenAI Agents SDK adapter
- OpenAI-compatible adapters
- Custom provider adapters (Gemini, llama.cpp, Ollama, TGI, others)

## Conformance Gates

## 1) Contract Compliance (Required)
- [ ] Implements `start_session`.
- [ ] Implements `run_turn`.
- [ ] Implements `submit_tool_results`.
- [ ] Implements `get_capabilities`.
- [ ] Implements `healthcheck`.
- [ ] Emits only internal `RuntimeEvent` shapes across the adapter boundary.

## 2) Envelope and Schema Compliance (Required)
- [ ] Accepts internal `ToolCallContext` schema (`v1`).
- [ ] Returns `ToolResult` schema (`v1`) with normalized `status`.
- [ ] Returns normalized error envelope (`code`, `category`, `message`, `retryable`).
- [ ] Supports schema version negotiation or explicit version rejection.

## 3) Safety and Policy Compliance (Required)
- [ ] Honors `PolicyDecision` outcomes (`allow`, `deny`, `escalate`).
- [ ] Does not execute blocked tool calls.
- [ ] Supports deterministic enforcement for state-changing/high-risk operations.
- [ ] Records reason codes for all policy-driven reroutes/blocks.

## 4) Observability Compliance (Required)
- [ ] Logs required IDs: `job_id`, `task_id`, `session_id`, `run_id`, `agent_id`, `call_id`, `provider_id`, `correlation_id`.
- [ ] Emits mode and decision dimensions: `mode_used`, `decision`, `reason_code`, `attempt`, `duration_ms`.
- [ ] Emits traces compatible with global timeline reconstruction.
- [ ] Includes provider adapter version in logs/metrics labels.

## 5) Reliability Compliance (Required)
- [ ] Handles timeout with normalized `timeout` status/error category.
- [ ] Handles cancellation with normalized `cancelled` status.
- [ ] Handles transient failures with retryable flags.
- [ ] Exposes `healthcheck` state (`healthy`, `degraded`, `down`) with reason.

## 6) Portability and Parity Compliance (Required)
- [ ] Runs canonical workflow parity suite against OpenAI baseline.
- [ ] Passes deterministic replay test for tool side-effect path.
- [ ] Supports fallback behavior when provider feature is unavailable.
- [ ] Does not require provider-name conditionals in orchestration core.

## 7) Security and Secrets Compliance (Required)
- [ ] Uses approved secret sources (env/Vault/KMS boundary).
- [ ] Redacts sensitive fields in logs.
- [ ] Declares `security_tier` in capability map.
- [ ] Enforces configured egress/network policy constraints.

## 8) Performance Compliance (Release Threshold)
- [ ] P50/P95 latency captured in test report.
- [ ] Throughput and error-rate within profile threshold.
- [ ] Cost-per-job (or token-per-job) baseline recorded.
- [ ] No unbounded memory growth under soak test profile.

## Evidence Pack (Must Attach)
- CI run link with adapter conformance suite.
- Workflow parity report (OpenAI baseline vs candidate adapter).
- Replay test report.
- Failure-injection report (timeouts, malformed outputs, provider unavailability).
- Observability sample bundle (logs/traces/metrics with required fields).

## Decision Rules
- Any failed required item => adapter cannot be promoted to production profile.
- Performance threshold misses => adapter can remain in experimental profile only.
- Security/policy failures => immediate block and incident ticket.

## Related Docs
- `10-provider-capability-matrix.md`
- `23-pr-release-evidence-templates.md`
- `31-tool-calling-contracts-and-mode-selection.md`
