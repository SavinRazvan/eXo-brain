<!--
File: customer-self-serve-governance-journey.md
Path: docs/strategy/customer-self-serve-governance-journey.md
Role: Customer self-serve governance journey — API stages, safe iteration, code anchors.
Used By:
 - README.md
 - AGENTS.md
 - docs/strategy/goal.md
 - docs/strategy/traceability-matrix.md
Depends On:
 - docs/plans/tenant-tool-execution-architecture.md
 - docs/strategy/entitlement-matrix.md
Notes:
 - API-first: no required UI; future UI is a thin client over the same endpoints.
-->

# Customer self-serve governance journey

## Governance metadata

| Field | Value |
|-------|-------|
| **Status** | `active` (baseline from product behavior; expand with customer-facing examples in follow-up edits) |
| **Scope** | Tenant-scoped governance via public APIs |

## Product intent

Customers configure **tenant-scoped governance** via API without a required UI. Every production turn uses the governed path documented in `docs/plans/tenant-tool-execution-architecture.md`.

## Journey stages (implemented today)

| Stage | Customer action | API / code | Tier notes |
|-------|-----------------|------------|------------|
| 1 Bootstrap tenant | Register providers, tools, agents | `providers.py`, `tools.py`, `agents.py` | Foundation+ |
| 2 Policy overlay | GET/PUT policy, apply templates | `tenants.py` (policy + template apply); `policy_templates.py` | Foundation+ |
| 3 Ingress profile | Configure profiles, custom rules, classifier | `ingress_profiles.py`; tenant overlay keys | Pro+ features gated |
| 4 Session + turn | Create session; SSE/WS/OpenAI gateway turn | `sessions.py`, `turns.py`, `openai_gateway.py` | Foundation+ |
| 5 Observe | Audit list/export; runtime stats | `audit.py`, `runtime_control.py` | Enterprise for signed export |
| 6 Iterate | Adjust overlay; re-run turns | Overlay store + hydration on startup | — |

## Safe iteration (today vs planned)

| Pattern | Today | Follow-up doc emphasis |
|---------|-------|------------------------|
| Non-prod tenant | Supported — separate `tenant_id` | Safe environments |
| Correlation-linked audit | `correlation_id` on turns/events | Feedback loop |
| Classifier shadow | Ingress classifier routing evidence fields | Shadow mode |
| Dry-run / simulation API | **Not implemented** — planned (IMP-06 / research stub `planned-docs/governance-preview-and-testing.STUB.md` under `_research_results/`) | Simulation |

## Configuration checklist (scope)

1. Tenant identity and roles (auth).
2. Providers, tool versions, agents.
3. Policy overlay and optional templates.
4. Ingress profile and compatibility settings (tier-gated where applicable).
5. Sessions and governed turns (SSE/WebSocket/REST).
6. Audit and runtime visibility (tier-gated).

## Precedence (summary)

- **Overlay vs template:** locked template keys cannot be overridden via `overlay_extra` (`_LOCKED_TEMPLATE_KEYS` in `policy_templates.py`).
- **Entitlements** gate feature access before overlay-only features apply on routes.
- **Non-bypass:** production traffic should not skip server-side policy and tool gates; see `docs/strategy/governed-execution-positioning.md`.

## Roles

- **Integrator** — wires auth, tenant bootstrap, and automation against the API.
- **Operator** — adjusts policy, quotas, ingress, and observability within entitlements.

## Code anchors (verification)

- Governed turn pipeline: `iter_governed_turn_dicts_for_transport` in `src/api/routers/turns.py`.
- Entitlements: `src/api/middleware/entitlements.py`, `src/policies/entitlements.py`.
- Templates: `compile_policy_template_overlay` in `policy_templates.py`.
- Traceability: `docs/strategy/traceability-matrix.md`.

## Link bundle

Start with `docs/README.md`, `README.md`, and `docs/plans/control-plane-product-alignment-plan.md` for vocabulary; keep this file aligned with `docs/strategy/entitlement-matrix.md` for tier semantics.
