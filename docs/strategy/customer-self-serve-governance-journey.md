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
| **Status** | `active` |
| **Last reviewed** | `2026-05-29` |
| **Scope** | Tenant-scoped governance via public APIs (`/tenants/{tenant_id}/...`) |

## Product intent

Customers configure **tenant-scoped governance** via API without a required UI. Every production turn uses the governed path documented in `docs/plans/tenant-tool-execution-architecture.md`.

## Journey stages (implemented today)

| Stage | Customer action | HTTP / code (see [customer-api-integration-guide.md](../api/customer-api-integration-guide.md)) | Tier notes |
|-------|-----------------|----------------------------------------------------------------------------------------|------------|
| 1 Bootstrap | Register providers (global), tools, agents | `POST /providers`; `POST /tenants/{tenant_id}/tools`; `POST /tenants/{tenant_id}/agents` | Foundation+ |
| 2 Policy overlay | GET/PUT policy; apply templates | `GET/PUT /tenants/{tenant_id}/policy`; `POST .../policy/templates/{id}/apply` | Foundation+; templates Pro-gated |
| 3 Ingress | Profiles, custom rules, classifier in overlay | `src/policies/ingress_*`; evaluated in `turns.py` before orchestrator | Pro+ where gated |
| 4 Session + turn | Create session; SSE/WS or optional `/v1` | `POST /tenants/{tenant_id}/sessions`; `POST .../sessions/{id}/turns`; optional `POST /v1/chat/completions` + `X-eXo-Session-Id` | Foundation+ |
| 5 Observe | Audit + runtime admin | `GET /tenants/{tenant_id}/admin/audit/*`; `.../admin/runtime/*` | Enterprise for signed export-file/verify |
| 6 Iterate | Adjust overlay; re-run turns | `policy_overlay` store; `src/api/startup.py` hydration | — |

## Safe iteration (today vs planned)

| Pattern | Today | Follow-up doc emphasis |
|---------|-------|------------------------|
| Non-prod tenant | Supported — separate `tenant_id` | Safe environments |
| Correlation-linked audit | `correlation_id` on turns/events | Feedback loop |
| Classifier shadow | Ingress classifier routing evidence fields | Shadow mode |
| Dry-run / simulation API | **Not implemented** — planned in-tree `docs/api/governance-preview-and-testing.md` (tracked in traceability-matrix) | Simulation |

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

- [docs/strategy/README.md](README.md) — strategy index  
- [customer-api-integration-guide.md](../api/customer-api-integration-guide.md) — wire contracts  
- [governed-execution-pipeline.md](../architecture/governed-execution-pipeline.md) — turn ordering  
- [entitlement-matrix.md](entitlement-matrix.md) — tier semantics  
- [control-plane-product-alignment-plan.md](../plans/control-plane-product-alignment-plan.md) — vocabulary
