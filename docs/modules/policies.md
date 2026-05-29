<!--
File: policies.md
Path: docs/modules/policies.md
Role: Module-level contract and maintenance guide for policy middleware, ingress, and risk gates.
Used By:
 - docs/modules/README.md
 - Maintainers modifying policy enforcement, ingress, and tenant policy overlays
Depends On:
 - src/policies/
 - src/api/routers/turns.py
 - src/observability/ingress_budget.py
 - tests/modules/policies/
 - docs/architecture/governed-execution-pipeline.md
Notes:
 - Ingress runs on the API turn path before orchestrator; tool policy runs inside the executor path.
-->

# Policies Module

## Metadata

- Status: `active`
- Owner: Savin I. Razvan
- Last validated commit: `HEAD`
- Last reviewed: `2026-05-29`

## Primary Code Paths

**Tool policy (orchestration path)**

- `src/policies/middleware.py` — `DeterministicFirstPolicyMiddleware` (`before_tool_call` / `after_tool_call`)
- `src/policies/risk_gates.py` — risk-tier gates
- `src/policies/tool_package_policy.py` — upload/register gates

**Ingress (API turn path — before `Orchestrator`)**

- `src/policies/ingress_gates.py` — gate chain builder + evaluation
- `src/policies/ingress_profiles.py` — `baseline` / `strict` / `hardened` profiles
- `src/policies/ingress_classifier_router.py` — classifier shadow/enforce (Pro+)
- `src/policies/ingress_signed_plugins.py` — signed plugin lifecycle (Enterprise)
- `src/api/routers/turns.py` — wires ingress + budget into SSE/WS turns
- `src/observability/ingress_budget.py` — latency budget recorder (alerts + admin summary API)

**Tenant governance inputs**

- `src/policies/policy_templates.py` — packaged templates (Pro+)
- `src/policies/entitlements.py` — feature keys; enforced in `src/api/middleware/entitlements.py`
- `src/policies/byoc_fairness.py` — BYOC fair admission (when enabled)
- `src/policies/governance_anomaly_detector.py` — BYOC governance metrics anomalies
- `src/tenancy/policy_overlay.py` — persisted overlay store (see [tenancy.md](tenancy.md))

## Primary Tests

- `tests/modules/policies/` — middleware, ingress chain, profiles, templates, entitlements, signed plugins
- `tests/modules/api/test_slice3_playground.py` — ingress allow/deny + audit correlation on HTTP turns
- `tests/modules/api/test_slice4_tenant_policy.py` — policy overlay + templates via API
- **Anchors:** `test_ingress_gate_chain.py`, `test_policy_middleware_abstract.py`, `test_entitlements.py`

## Contract Boundaries

- `before_tool_call` decides `allow` / `deny` / `escalate` (`PolicyAction`). On the reference orchestration path, any decision **other than `allow`** stops registered-handler execution: **`deny`** and **`escalate`** both yield a **blocked-style** tool envelope from `DeterministicToolExecutor` (for example `ToolStatus.BLOCKED` with `POLICY_BLOCKED` and `error.details.reason_code`). **`escalate`** additionally sets **`review_required`** and **`review_channel`** on the `PolicyDecision` for operators; there is **no** in-core human approval queue yet (see [traceability-matrix.md](../strategy/traceability-matrix.md), Human approval workflow surface).
- `after_tool_call` validates post-execution outcomes and consistency (audit `correlation_id`, deterministic `mode_used` on success paths, and success payload invariants in `DeterministicFirstPolicyMiddleware`). All envelopes returned from `DeterministicToolExecutor.execute` pass through this hook.
- **Ingress:** non-`allow` decisions stop the HTTP/SSE/WS turn before `Orchestrator.run_turn` ([governed-execution-pipeline.md](../architecture/governed-execution-pipeline.md)).
- Policy logic must not be bypassed for risky/state-changing operations.

## Operational Links

- [governed-execution-pipeline.md](../architecture/governed-execution-pipeline.md)
- [customer-api-integration-guide.md](../api/customer-api-integration-guide.md) — tiers, ingress profiles, audit correlation
- [traceability-matrix.md](../strategy/traceability-matrix.md)
- [option-c-performance-gates.md](../plans/option-c-performance-gates.md)
- [release-candidate-signoff-checklist.md](../operations/release-candidate-signoff-checklist.md)

## Breaking-Change Policy

- Any update to policy decision semantics, ingress profiles, or risk-tier handling requires:
  - explicit regression tests in `tests/modules/policies/` and affected API tests
  - reason-code documentation updates (planned catalog: `docs/operations/governance-reason-code-catalog.md`)
  - architecture gate verification before merge
