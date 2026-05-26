<!--
File: policies.md
Path: docs/modules/policies.md
Role: Module-level contract and maintenance guide for policy middleware and risk gates.
Used By:
 - Maintainers modifying policy enforcement, risk gating, and tenant policy overlays
Depends On:
 - src/policies/
 - tests/modules/policies/
 - docs/architecture/governed-execution-pipeline.md
Notes:
 - Policy checks are mandatory on side-effecting tool execution paths.
-->

# Policies Module

## Metadata

- Status: `active`
- Owner: Savin I. Razvan
- Last validated commit: `HEAD`

## Primary Code Paths

- `src/policies/middleware.py`
- `src/policies/risk_gates.py`
- `src/policies/byoc_fairness.py`
- `src/policies/tool_package_policy.py`

## Primary Tests

- `tests/modules/policies/`

## Contract Boundaries

- `before_tool_call` decides `allow` / `deny` / `escalate` (`PolicyAction`). On the reference orchestration path, any decision **other than `allow`** stops registered-handler execution: **`deny`** and **`escalate`** both yield a **blocked-style** tool envelope from `DeterministicToolExecutor` (for example `ToolStatus.BLOCKED` with `POLICY_BLOCKED` and `error.details.reason_code`). **`escalate`** additionally sets **`review_required`** and **`review_channel`** on the `PolicyDecision` for operators; there is **no** in-core human approval queue yet (see `docs/strategy/traceability-matrix.md`, Human approval workflow surface).
- `after_tool_call` validates post-execution outcomes and consistency (audit `correlation_id`, deterministic `mode_used` on success paths, and success payload invariants in `DeterministicFirstPolicyMiddleware`). All envelopes returned from `DeterministicToolExecutor.execute` pass through this hook.
- Policy logic must not be bypassed for risky/state-changing operations.

## Operational Links

- [`docs/architecture/governed-execution-pipeline.md`](../architecture/governed-execution-pipeline.md) — canonical ordering of ingress, orchestrator, policy, and executor.
- [`docs/api/customer-api-integration-guide.md`](../api/customer-api-integration-guide.md) — tier-aware turn and audit behavior.
- [`docs/strategy/traceability-matrix.md`](../strategy/traceability-matrix.md) — governance rows, tests, and planned approval workflow.
- `docs/plans/option-c-performance-gates.md`
- `docs/operations/release-candidate-signoff-checklist.md`

## Breaking-Change Policy

- Any update to policy decision semantics or risk-tier handling requires:
  - explicit regression tests
  - reason-code documentation updates
  - architecture gate verification before merge
