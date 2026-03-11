<!--
File: tenancy.md
Path: docs/modules/tenancy.md
Role: Module-level contract and maintenance guide for tenant isolation, quotas, and rate limiting.
Used By:
 - Maintainers modifying tenant admission/fairness/isolation behavior
Depends On:
 - src/tenancy/
 - src/runtime/tenant_runtime.py
 - tests/modules/runtime/
 - tests/modules/api/
Notes:
 - Tenant isolation is a hard boundary and must be enforced across control and data planes.
-->

# Tenancy Module

## Metadata

- Status: `active`
- Owner: Savin I. Razvan
- Last validated commit: `HEAD`

## Primary Code Paths

- `src/tenancy/tenant_context.py`
- `src/tenancy/quotas.py`
- `src/tenancy/rate_limiter.py`
- `src/runtime/tenant_runtime.py`

## Primary Tests

- `tests/modules/runtime/test_tenant_runtime.py`
- `tests/modules/core/test_shared_state_backends.py`
- `tests/modules/api/test_slice4_tenant_policy.py`

## Contract Boundaries

- Every tenant receives isolated runtime context (tools/agents/policy/session stores).
- Admission controls enforce fairness and bounded concurrency.
- Shared state backends must preserve deterministic cross-instance behavior.

## Operational Links

- `docs/plans/option-c-worker-isolation-contract.md`
- `docs/plans/option-c-performance-gates.md`
- `docs/operations/byoc-failure-injection-playbook.md`

## Breaking-Change Policy

- Any change affecting tenant isolation or admission semantics requires:
  - explicit multi-tenant regression coverage
  - policy + runtime documentation updates
  - release signoff review for fairness/SLO impact
