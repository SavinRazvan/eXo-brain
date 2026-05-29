<!--
File: foundation-tier-adoption-checklist.md
Path: docs/strategy/foundation-tier-adoption-checklist.md
Role: Foundation-tier minimum adoption steps with Pro/Enterprise deltas.
Used By:
 - README.md
 - AGENTS.md
 - docs/strategy/goal.md
Depends On:
 - docs/strategy/entitlement-matrix.md
 - docs/plans/control-plane-product-alignment-plan.md
Notes:
 - Add curl examples in a customer API guide slice; keep tier truth in entitlement-matrix.md.
-->

# Foundation tier adoption checklist

## Governance metadata

| Field | Value |
|-------|-------|
| **Status** | `active` (baseline checklist) |
| **Scope** | Foundation tier minimum path to a governed turn |

## Foundation tier — minimum viable adoption

Based on `EntitledFeature` / `EntitlementTier` in `src/policies/entitlements.py` and enforcement in `src/api/middleware/entitlements.py`.

| Step | Task | Endpoint / module | Done when |
|------|------|-------------------|-----------|
| 1 | Configure auth (JWT or API key) | `admin_keys.py`, `auth.py` | 401/403 behave as expected |
| 2 | Register provider | `POST` providers | Provider in registry |
| 3 | Register tool (+ optional package) | `tools.py` | Tool resolves in registry |
| 4 | Create agent | `agents.py` | Agent spec loadable |
| 5 | Set baseline policy overlay | `tenants.py` policy routes | GET policy returns overlay |
| 6 | Create session | `sessions.py` | Session id returned |
| 7 | Submit governed turn (SSE or WS) | `turns.py` | Stream receives events |
| 8 | Query audit (if entitled) | `audit.py` | Events visible for tenant |

## Pro / Enterprise deltas (pointer only)

| Capability | Foundation | Higher tier |
|------------|------------|-------------|
| Policy templates | Limited / gated | Pro+ apply template APIs |
| Classifier shadow/enforce | Gated | Pro+ |
| BYOC fairness analytics | Gated | Pro+ `runtime_control.py` |
| Signed audit export | Gated | Enterprise `audit.py` export |

Authoritative matrix: `docs/strategy/entitlement-matrix.md`.

## Operational defaults

| Setting | Location |
|---------|----------|
| SQLite DB | `EXO_DB_PATH` default `.exo_data/exo.db` |
| Ingress budget fail mode | overlay / settings → `ingress_budget.py` |
| Prometheus | `EXO_ENABLE_PROMETHEUS_METRICS=1` |

## Documentation follow-ups

- Copy-paste HTTP examples per step: [`docs/api/customer-api-integration-guide.md`](../api/customer-api-integration-guide.md) §15 (full paths under `/tenants/...`).
- Explicit Foundation-only feature list with sample 403 responses.
- Upgrade path bullets to Pro/Enterprise without duplicating `entitlement-matrix.md`.
