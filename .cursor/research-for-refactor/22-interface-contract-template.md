# Interface Contract Template

## Goal
Provide a reusable template for defining stable module interfaces (adapters, tools, policies, stores, and workflows).

## Template

## 1) Interface Metadata
- Name:
- Module:
- Version:
- Owner:
- Stability: (`experimental` | `beta` | `stable`)

## 2) Purpose and Responsibilities
- What this interface does:
- What this interface must not do:

## 3) Input Contract
- Required fields:
- Optional fields:
- Validation rules:
- Max payload/limits:

## 4) Output Contract
- Success envelope:
- Error envelope:
- Partial/fallback behavior:

## 5) Operational Contract
- Timeout defaults:
- Retry policy:
- Idempotency requirements:
- Circuit-breaker behavior:

## 6) Security and Policy Contract
- Required auth/authz context:
- Risk tier:
- Policy hooks (`pre`, `post`, `on_error`):
- Audit fields:

## 7) Observability Contract
- Required correlation fields:
- Metrics emitted:
- Trace spans/events:
- Timeline reconstruction fields:

## 8) Compatibility and Versioning
- Backward compatibility guarantees:
- Breaking-change policy:
- Deprecation timeline:

## 9) Test Contract
- Unit cases:
- Integration cases:
- Failure and chaos cases:
- Deterministic replay cases:

## 10) Rollout and Rollback
- Rollout strategy:
- Rollback trigger:
- Safe fallback behavior:

## Contract Pack Recommendation (For Runtime + Tooling)
- Runtime boundary: include `get_capabilities` and `healthcheck` in adapter contracts.
- Tool call path: define `ToolCallContext`, `PolicyDecision`, and `ToolResult` as versioned schemas.
- Execution policy: document explicit mode selection rules (`provider_native` vs `deterministic`) with reason codes.
- Auditability: require correlation IDs and normalized error categories in every envelope.

## Related Docs
- `08-module-requirements-matrix.md`
- `10-provider-capability-matrix.md`
- `16-enterprise-testing-strategy.md`
- `31-tool-calling-contracts-and-mode-selection.md`
