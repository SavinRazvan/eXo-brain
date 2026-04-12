<!--
File: policies.md
Path: docs/modules/policies.md
Role: Module-level contract and maintenance guide for policy middleware and risk gates.
Used By:
 - Maintainers modifying policy enforcement, risk gating, and tenant policy overlays
Depends On:
 - src/policies/
 - tests/modules/policies/
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

- `before_tool_call` decides `allow` / `deny` / `escalate`.
- `after_tool_call` validates post-execution outcomes and consistency.
- Policy logic must not be bypassed for risky/state-changing operations.

## Operational Links

- `docs/plans/option-c-performance-gates.md`
- `docs/operations/release-candidate-signoff-checklist.md`
- `docs/operations/governance-reason-code-catalog.md`
- `docs/api/governance-preview-and-testing.md`

## Breaking-Change Policy

- Any update to policy decision semantics or risk-tier handling requires:
  - explicit regression tests
  - reason-code documentation updates
  - architecture gate verification before merge
