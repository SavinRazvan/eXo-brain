<!--
File: tenancy.md
Path: docs/modules/tenancy.md
Role: Module-level contract and maintenance guide for tenant isolation, quotas, rate limits, and policy overlays.
Used By:
 - docs/modules/README.md
 - Maintainers modifying tenant admission/fairness/isolation behavior
Depends On:
 - src/tenancy/
 - src/runtime/tenant_runtime.py
 - src/modules/tenant_governance/service.py
 - src/api/middleware/entitlements.py
 - tests/modules/tenancy/
 - tests/modules/runtime/
 - tests/modules/api/
Notes:
 - Tenant isolation is a hard boundary across control and data planes.
-->

# Tenancy Module

## Metadata

- Status: `active`
- Owner: Savin I. Razvan
- Last validated commit: `HEAD`
- Last reviewed: `2026-05-29`

## Primary Code Paths

- `src/tenancy/tenant_context.py` — tenant-scoped context handles
- `src/tenancy/policy_overlay.py` — get/set overlay used by ingress + tool policy
- `src/tenancy/quotas.py` — turn/upload quotas and active-run caps
- `src/tenancy/rate_limiter.py` — per-tenant rate limits (memory + SQLite backends)
- `src/runtime/tenant_runtime.py` — isolated registries per tenant (tools, agents, adapter)
- `src/modules/tenant_governance/service.py` — modular slice for governance wiring
- `src/api/middleware/entitlements.py` — tier enforcement + `entitlement_decision` audit events
- `src/api/routers/tenants.py` — `GET/PUT /tenants/{tenant_id}/policy`, quota, templates

## Primary Tests

- `tests/modules/tenancy/test_rate_limiter_edges.py`
- `tests/modules/runtime/test_tenant_runtime.py`
- `tests/modules/core/test_shared_state_backends.py`
- `tests/modules/api/test_slice4_tenant_policy.py`
- `tests/modules/persistence/test_cross_tenant_isolation.py`

## Contract Boundaries

- Every tenant receives an isolated runtime context (tools, agents, policy overlay, session stores).
- Admission controls (rate limits, quotas, BYOC fairness when enabled) enforce bounded concurrency with structured reason codes.
- Shared state backends must preserve deterministic cross-instance behavior where used.
- Entitlement tier checks are **server-side** on premium surfaces; clients cannot downgrade tier labels.

## Operational Links

- [customer-api-integration-guide.md](../api/customer-api-integration-guide.md) §8 — policy overlay and quota HTTP routes
- [entitlement-matrix.md](../strategy/entitlement-matrix.md)
- [option-c-worker-isolation-contract.md](../plans/option-c-worker-isolation-contract.md)
- [option-c-performance-gates.md](../plans/option-c-performance-gates.md)
- [byoc-failure-injection-playbook.md](../operations/byoc-failure-injection-playbook.md)

## Breaking-Change Policy

- Any change affecting tenant isolation, overlay schema, or admission semantics requires:
  - explicit multi-tenant regression coverage
  - policy + API documentation updates
  - release signoff review for fairness/SLO impact
