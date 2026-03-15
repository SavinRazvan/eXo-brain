<!--
File: customer-api-integration-guide.md
Path: docs/api/customer-api-integration-guide.md
Role: Tier-aware API contract documentation for customer onboarding across chat/agents/workflow and governance ingress surfaces.
Used By:
 - docs/plans/docs-inventory-master.md
 - architecture-goals/TRACEABILITY_MATRIX.md
 - README.md
Depends On:
 - src/api/routers/turns.py
 - src/api/routers/tenants.py
 - src/api/routers/runtime_control.py
 - src/api/routers/agents.py
 - src/api/routers/tools.py
 - src/api/routers/audit.py
 - src/api/routers/providers.py
 - architecture-goals/ENTITLEMENT_MATRIX.md
 - architecture-goals/INTERFACE_STRATEGY.md
Notes:
 - Keep tier labels in sync with architecture-goals/ENTITLEMENT_MATRIX.md.
 - All safety and governance controls are server-side and non-bypassable regardless of tier.
-->

# eXo-brain Customer API Integration Guide

## Document Governance

- Status: `active`
- Owner: `Savin I. Razvan`
- Version: `1.0.0`
- Last Reviewed: `2026-03-15`
- Review Cadence: `on architecture change`

---

## 1) Overview

eXo-brain is an API-first AI orchestration platform. All capabilities are available via REST, SSE, and WebSocket endpoints. There is no required backend-served UI; customers build their own interfaces on top of these APIs.

Every turn request passes through a mandatory server-side governance ingress path before model or tool execution. This path cannot be bypassed by any client.

---

## 2) Authentication

All endpoints require one of the following authentication methods (evaluated in precedence order):

| Method | Header | Notes |
|---|---|---|
| Bearer JWT | `Authorization: Bearer <jwt>` | Preferred for user-scoped identity |
| Bearer API key | `Authorization: Bearer <api-key>` | Preferred for service-to-service |
| Header API key | `X-API-Key: <api-key>` | Alternative for service-to-service |
| X-Identity (dev only) | `X-Identity: <tenant-id>` | Blocked in production environments |

API keys are managed via `POST /admin/keys` (admin scope required). JWT secrets are configured in `AuthSettings`.

---

## 3) Tier Summary

Features are packaged by tier. All server-side safety controls apply regardless of tier.

| Tier | Scope |
|---|---|
| **Foundation** | Core turn execution, provider registration, tool/agent lifecycle, policy overlay, quota, basic audit access |
| **Pro** | Advanced runtime admin, agent routing/fallback governance, BYOC governance analytics, policy templates, custom gate rules, classifier controls |
| **Enterprise** | Signed audit export/verification, signed custom gate plugins, advanced fairness/admission controls, release signoff evidence bundles |

Tier enforcement is applied at the API layer via `src/api/middleware/entitlements.py`. Unauthorized tier access returns `403` with an `entitlement_decision` audit record.

---

## 4) Turn Execution (Chat / Agents / Workflow)

### 4.1) SSE Turn

Submit a turn and receive a streaming Server-Sent Events response.

```
POST /{tenant_id}/sessions/{session_id}/turns
Content-Type: application/json
Authorization: Bearer <token>
Accept: text/event-stream
```

**Request body** (abbreviated):
```json
{
  "input": "Hello, what is the weather in Bucharest?",
  "run_config": {
    "max_tool_calls": 5,
    "timeout_ms": 30000
  }
}
```

**SSE event stream** — the server emits a sequence of typed events:
- `progress` — intermediate reasoning or tool call steps
- `tool_call_result` — outcome of a tool execution
- `ingress_budget_alert` — emitted when the ingress latency budget is exceeded (non-blocking unless fail-closed)
- `done` — final turn output

**Governance ingress** runs before orchestration for every turn:
1. Entitlement check (tier-gated features)
2. Ingress gate chain (profile-matched predefined + custom rules)
3. Latency budget evaluation (profile-specific p95 threshold + timeout fail-safe)

If the gate chain returns `deny`, the stream emits a `403` response with a reason code. If a timeout occurs with `fail_closed` mode, the turn is rejected. With `fail_open`, the turn proceeds and a budget alert event is emitted.

### 4.2) WebSocket Turn

```
WS /{tenant_id}/sessions/{session_id}/ws
```

Semantics are equivalent to the SSE path. The WebSocket connection receives the same typed event sequence.

### 4.3) Ingress Profiles

The ingress gate chain is profile-scoped. Available predefined profiles:

| Profile | Overhead | Use case |
|---|---|---|
| `baseline` | Minimal | Standard production traffic |
| `strict` | Moderate | Higher-sensitivity workloads |
| `hardened` | Maximum | Compliance-sensitive or high-risk sessions |

Profile is set via the tenant policy overlay (`PUT /{tenant_id}/policy`). The active profile is reflected in `turn_ingress_decision` audit events and ingress budget observations.

---

## 5) Provider Registration (Foundation)

Register, list, and deregister model providers. Providers are identified by contract and capability, never by hardcoded name in core orchestration.

```
POST   /providers
GET    /providers
DELETE /providers/{provider_id}
GET    /providers/{provider_id}/health
GET    /providers/{provider_id}/capabilities
```

Provider registration is required before turns can be executed against a given provider.

---

## 6) Tool Lifecycle (Foundation)

Manage tenant-scoped tools. All tool registration paths enforce upload policy gates (size, dependency scan).

```
POST   /{tenant_id}/tools                          # register tool
POST   /{tenant_id}/tools/upload                   # upload tool package
POST   /{tenant_id}/tools/import-schema            # import tool schema from URL
GET    /{tenant_id}/tools                          # list tools
GET    /{tenant_id}/tools/{name}                   # get tool
DELETE /{tenant_id}/tools/{name}                   # unregister tool
GET    /{tenant_id}/tools/versions/{tool_name}     # list versions
GET    /{tenant_id}/tools/validate/{tool_name}     # validate version
POST   /{tenant_id}/tools/{name}/deactivate/{ver}  # deactivate version
POST   /{tenant_id}/tools/{name}/rollback          # rollback to prior version
DELETE /{tenant_id}/tools/{name}/versions/{ver}    # revoke version
```

Tool state changes produce audit events in the turn audit chain.

---

## 7) Agent Lifecycle (Foundation + Pro)

Manage tenant-scoped agents. Advanced routing and fallback controls are Pro-tier.

```
POST   /{tenant_id}/agents                  # register agent (Foundation)
GET    /{tenant_id}/agents                  # list agents (Foundation)
GET    /{tenant_id}/agents/{agent_id}       # get agent (Foundation)
DELETE /{tenant_id}/agents/{agent_id}       # unregister agent (Foundation)
POST   /{tenant_id}/agents/routes           # add handoff route (Pro)
GET    /{tenant_id}/agents/routes           # list handoff routes (Pro)
POST   /{tenant_id}/agents/fallback         # set fallback policy (Pro)
GET    /{tenant_id}/agents/fallback         # list fallback policies (Pro)
```

Routing/fallback operations are gated by `entitlement_decision` at the API layer.

---

## 8) Tenant Policy and Governance (Foundation + Pro)

### 8.1) Policy Overlay (Foundation)

Get and set the tenant's active governance policy, including ingress profile, quota, and custom gate rules.

```
GET  /{tenant_id}/policy     # get current policy overlay
PUT  /{tenant_id}/policy     # set/update policy overlay
```

**Policy overlay fields** (abbreviated):
```json
{
  "ingress_profile": "strict",
  "custom_rules": [
    {
      "rule_id": "block-pii",
      "field": "input",
      "op": "contains",
      "value": "SSN",
      "action": "deny",
      "reason_code": "PII_DETECTED"
    }
  ],
  "classifier": {
    "mode": "shadow",
    "model_ref": "heuristic-v1"
  }
}
```

Policy changes emit `tenant_policy_ingress_profile_configured` audit events.

### 8.2) Policy Templates (Pro)

Apply a packaged risk-profile template. Templates cannot override locked ingress fields.

```
GET  /{tenant_id}/policy/templates                          # list available templates
POST /{tenant_id}/policy/templates/{template_id}/apply     # apply template
```

Apply modes: `merge` (extends existing policy) or `replace` (replaces policy).

### 8.3) Quota Controls (Foundation)

```
GET /{tenant_id}/quota    # get current quota settings
PUT /{tenant_id}/quota    # update quota settings
```

Quota controls enforce per-tenant turn rate limits, upload rate limits, and active-run concurrency caps.

---

## 9) Runtime Admin Controls (Pro)

Pro-tier controls for operational visibility and run management.

```
GET    /{tenant_id}/admin/runtime/stats                    # runtime stats
GET    /{tenant_id}/admin/runtime/cleanup-events           # cleanup events log
POST   /{tenant_id}/admin/runtime/cancel                   # request cancellation
DELETE /{tenant_id}/admin/runtime/cancel                   # clear cancellation
GET    /{tenant_id}/admin/runtime/runs                     # list active runs
GET    /{tenant_id}/admin/runtime/runs/{run_id}            # get run
POST   /{tenant_id}/admin/runtime/runs/{run_id}/cancel     # cancel run
GET    /{tenant_id}/admin/runtime/ingress-budget           # per-profile ingress budget summary
```

### 9.1) Ingress Budget Summary

Returns per-profile SLO observations for the tenant:

```json
{
  "tenant_id": "tenant-123",
  "generated_at_utc": "2026-03-15T06:00:00Z",
  "summary": {
    "samples": 1200,
    "p95_latency_ms": 18.4,
    "timeout_total": 3,
    "timeout_rate": 0.0025,
    "budget_exceeded_total": 7
  },
  "profiles": {
    "baseline": { "samples": 800, "p95_latency_ms": 12.1, ... },
    "strict":   { "samples": 300, "p95_latency_ms": 22.5, ... },
    "hardened": { "samples": 100, "p95_latency_ms": 31.2, ... }
  }
}
```

---

## 10) Audit and Compliance (Foundation + Enterprise)

### 10.1) Audit Events and Reports (Foundation)

```
GET  /{tenant_id}/admin/audit/events     # list audit events (filterable)
GET  /{tenant_id}/admin/audit/report     # summary audit report
POST /{tenant_id}/admin/audit/cleanup    # cleanup old events
```

### 10.2) Signed Audit Export and Verification (Enterprise)

```
GET  /{tenant_id}/admin/audit/export            # export audit bundle (JSON)
POST /{tenant_id}/admin/audit/export-file       # export signed bundle to file
POST /{tenant_id}/admin/audit/verify            # verify signed audit bundle
```

Signed audit bundles include a chain-integrity hash. `POST /verify` validates the signature server-side and returns a verification verdict.

---

## 11) Key Audit Event Types

All audit events include a `correlation_id` that links events across a single turn lifecycle.

| Event | Description | Tier |
|---|---|---|
| `turn_ingress_decision` | Allow/deny/escalate outcome from the ingress gate chain | Foundation |
| `turn_ingress_budget_alert` | Emitted when ingress latency budget is exceeded | Foundation |
| `turn_ingress_classifier_telemetry` | Classifier outcome and mode (shadow/enforce) | Pro |
| `turn_ingress_signed_plugin_telemetry` | Signed plugin load/evaluation outcome | Enterprise |
| `tenant_policy_ingress_profile_configured` | Tenant ingress profile change | Foundation |
| `tenant_policy_template_applied` | Policy template apply outcome | Pro |
| `tenant_policy_signed_gate_plugin_lifecycle` | Signed plugin load/reload/unload lifecycle | Enterprise |
| `entitlement_decision` | Tier enforcement decision on premium surface access | Cross-tier |

---

## 12) Safety Invariants (Non-Negotiable)

Regardless of tier or configuration, the following are always enforced server-side:

1. Every turn passes through the ingress gate chain before model or tool execution.
2. Policy middleware wraps all state-changing tool side effects.
3. Risky or state-changing tool calls use deterministic execution paths.
4. Tenant isolation is enforced for tools, agents, sessions, and policy overlays.
5. Audit events are generated server-side and cannot be disabled on risky paths.
6. Entitlement decisions are enforced at the API layer and cannot be bypassed by the client.
7. Identity and access control are server-side, not client-delegated.

---

## 13) BYOC (Bring Your Own Compute) Runtime Controls (Pro)

For tenants operating BYOC worker pools:

```
POST /{tenant_id}/admin/runtime/byoc/worker-token          # issue worker token
POST /{tenant_id}/admin/runtime/byoc/claim-job             # claim pending job
POST /{tenant_id}/admin/runtime/byoc/submit-result         # submit job result
POST /{tenant_id}/admin/runtime/byoc/webhook-result        # submit result via webhook
POST /{tenant_id}/admin/runtime/byoc/cleanup-retention     # clean up retention
GET  /{tenant_id}/admin/runtime/byoc/dead-letter           # list dead-letter jobs
POST /{tenant_id}/admin/runtime/byoc/dead-letter/replay    # replay dead-letter job
GET  /{tenant_id}/admin/byoc/governance-metrics            # BYOC governance analytics (Pro)
```

---

## 14) Error Response Format

All API errors return a JSON body with:

```json
{
  "detail": "<human-readable reason>",
  "reason_code": "<machine-readable code>",
  "correlation_id": "<uuid>"
}
```

Common governance-related reason codes:

| Reason Code | Meaning |
|---|---|
| `INGRESS_ALLOW_DEFAULT` | Turn allowed by default path |
| `INGRESS_GATE_DENY_*` | Turn denied by a named gate |
| `INGRESS_GATE_TIMEOUT_FAIL_CLOSED` | Ingress gate timed out; fail-closed mode denied the turn |
| `INGRESS_GATE_TIMEOUT_FAIL_OPEN` | Ingress gate timed out; fail-open mode allowed the turn |
| `ENTITLEMENT_TIER_REQUIRED` | Endpoint requires a higher tier |
| `QUOTA_EXCEEDED` | Tenant quota limit reached |

---

## 15) Integration Quickstart

### Step 1: Register a provider

```bash
curl -X POST https://<host>/providers \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"provider_id": "openai-gpt4o", "backend_id": "openai", "model": "gpt-4o"}'
```

### Step 2: Register a tool

```bash
curl -X POST https://<host>/tenant-123/tools \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"name": "weather", "description": "Get current weather", "handler_ref": "tools.weather:get_weather", "schema": {...}}'
```

### Step 3: Submit a turn (SSE)

```bash
curl -N -X POST https://<host>/tenant-123/sessions/session-abc/turns \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{"input": "What is the weather in Bucharest?"}'
```

### Step 4: Set an ingress profile

```bash
curl -X PUT https://<host>/tenant-123/policy \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"ingress_profile": "strict"}'
```

---

## 16) References

- `architecture-goals/ENTITLEMENT_MATRIX.md` — authoritative tier-to-feature mapping
- `architecture-goals/INTERFACE_STRATEGY.md` — API-first design rules and safety constraints
- `architecture-goals/TRACEABILITY_MATRIX.md` — strategy-to-code-to-test anchors
- `src/api/routers/` — canonical endpoint implementations
- `docs/operations/release-candidate-signoff-checklist.md` — release evidence requirements
