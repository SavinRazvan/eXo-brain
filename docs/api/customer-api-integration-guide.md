<!--
File: customer-api-integration-guide.md
Path: docs/api/customer-api-integration-guide.md
Role: Tier-aware API contract documentation for customer onboarding across chat/agents/workflow and governance ingress surfaces.
Used By:
 - docs/plans/docs-inventory-master.md
 - docs/strategy/traceability-matrix.md
 - README.md
Depends On:
 - src/api/routers/turns.py
 - src/api/routers/tenants.py
 - src/api/routers/runtime_control.py
 - src/api/routers/agents.py
 - src/api/routers/tools.py
 - src/api/routers/audit.py
 - src/api/routers/providers.py
 - src/api/routers/openai_gateway.py
 - src/observability/telemetry_export.py
 - src/api/routers/prometheus_metrics.py
 - src/api/bootstrap.py
 - docs/strategy/entitlement-matrix.md
 - docs/strategy/interface-strategy.md
 - docs/strategy/governed-execution-positioning.md
 - docs/plans/control-plane-product-alignment-plan.md
Notes:
 - Keep tier labels in sync with docs/strategy/entitlement-matrix.md.
 - All safety and governance controls are server-side and non-bypassable regardless of tier.
 - **Telemetry export — partial (productized baseline):** optional OTLP HTTP traces/metrics via env (`telemetry_export.py`, wired from `bootstrap.py`) and optional `GET /metrics` (Prometheus text, minimal `exo_build_info`) when `EXO_ENABLE_PROMETHEUS_METRICS=1` (`prometheus_metrics.py`). Not a full enterprise observability product: no guaranteed collector E2E in CI, limited metric catalog vs roadmap. See §9.2.
-->

# eXo-brain Customer API Integration Guide

## Document Governance

- Status: `active`
- Owner: `Savin I. Razvan`
- Version: `1.6.0`
- Last Reviewed: `2026-03-27`
- Review Cadence: `on architecture change`

---

## 1) Overview

eXo-brain is an API-first governed execution platform for tool-using AI systems. All capabilities are available via REST, SSE, and WebSocket endpoints. There is no required backend-served UI; customers build their own interfaces on top of these APIs.

Every turn request passes through a mandatory server-side governance ingress path before model or tool execution. This path cannot be bypassed by any client.

Integration boundary:
- customers can keep provider credentials and **provider runtime adapter** configuration in their own deployment environment (outbound connectivity to models),
- eXo-brain owns the **control plane** governed execution boundary: policy, deterministic tool execution, audit, runtime control, and operational visibility.

**Vocabulary (enterprise / partner conversations):** Do not overload “adapter.” **Provider runtime adapters** are how the *platform* reaches providers (`packages/*`, `src/runtime/*`). **Customer bridge** surfaces are how *your* apps call the control plane with less integration friction — today optional **`POST /v1/chat/completions`** (§4.0); a future thin SDK must share the same governance spine. Canonical definitions: [`docs/strategy/governed-execution-positioning.md`](../strategy/governed-execution-positioning.md), [`docs/plans/control-plane-product-alignment-plan.md`](../plans/control-plane-product-alignment-plan.md).

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

### 4.0) Optional OpenAI-compatible `POST /v1/chat/completions` (feature-flagged)

When **`EXO_ENABLE_OPENAI_COMPAT_GATEWAY=1`**, the platform exposes a **non-streaming** subset of the OpenAI Chat Completions API for clients that want familiar JSON shapes. This is a **customer bridge** convenience surface ([`interface-strategy.md`](../strategy/interface-strategy.md) Layer A2), not a second execution path: it uses the **same governance path** as SSE turns (entitlements, ingress, rate limits, run registry, host adapter).

| Item | Detail |
|------|--------|
| Endpoint | `POST /v1/chat/completions` |
| Auth | Same as §2 (Bearer JWT, Bearer API key, `X-API-Key`, or dev `X-Identity`) |
| Tenant | Taken from the authenticated identity’s `tenant_id` (no `{tenant_id}` in the path) |
| Session | Required header **`X-eXo-Session-Id`** — must be a session created under that tenant via `POST /tenants/{tenant_id}/sessions` |
| Streaming | `stream: true` is **not** supported in this MVP (returns **400**) |

Full URL map, middleware order, and non-goals: [`docs/archive/plans/northbound-v1-gateway.md`](../archive/plans/northbound-v1-gateway.md).

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

Provider registration is metadata for governed execution and routing. In production profiles, provider credentials and provider-native adapter configuration may remain customer-owned or deployment-owned rather than being treated as a required eXo-brain-hosted secret surface.

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

### 9.2) Standard telemetry export (**partial** — baseline shipped)

**Status:** *Partial.* Code exists and is covered by tests; treat rich operational telemetry (full metric catalog, collector certification, redaction SLOs) as **roadmap**, not a completed product surface.

**Already available**

| Mechanism | What it does | Configuration / code |
|-----------|----------------|----------------------|
| OTLP HTTP (traces + metrics) | When endpoints are set, `bootstrap_app()` configures OTLP span + metric exporters (OpenTelemetry SDK). | Env: `OTEL_EXPORTER_OTLP_ENDPOINT` and/or `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT`, `OTEL_EXPORTER_OTLP_METRICS_ENDPOINT`, optional `OTEL_SERVICE_NAME`, `OTEL_SERVICE_VERSION`, `OTEL_METRIC_EXPORT_INTERVAL_MS`. Implementation: `src/observability/telemetry_export.py` (`configure_opentelemetry_exporters`), invoked from `src/api/bootstrap.py`. |
| Prometheus text | Optional scrape endpoint exposing minimal process metadata (`exo_build_info`). | Env: `EXO_ENABLE_PROMETHEUS_METRICS=1`. Route: `GET /metrics`. Implementation: `src/api/routers/prometheus_metrics.py`, registered from `src/api/app.py`. |

**Tests (anchors):** `tests/modules/observability/test_telemetry_export.py`, `tests/modules/api/test_app_factory_branches.py` (`test_prometheus_metrics_router_registered_when_env_enabled`).

**Still on the roadmap (not claimed as done here)**

- End-to-end validation against a reference OTLP collector in CI / release gates.
- Broader runtime signal coverage in Prometheus/OTel exports (beyond build metadata and SDK defaults).
- Deployment-profile-specific redaction guarantees and exporter health checks as first-class certification artifacts.

Runtime visibility **today** also remains available through runtime-control APIs, audit APIs, and correlation-linked events. Exporters are **additive**; they do not replace audit evidence or runtime admin APIs.

---

## 10) Audit and Compliance (Foundation + Enterprise)

### 10.0) Correlating turns, ingress, and audit (Foundation)

Integrators should carry **one correlation identifier per logical turn** from the client through streams and into audit queries:

1. **SSE turns** — Optional `correlation_id` in the JSON body of `POST /{tenant_id}/sessions/{session_id}/turns`. If omitted, the server generates a short id. Streamed `data:` JSON events repeat `correlation_id` on payloads where the field applies (errors, tool progress, completion). Implementation: `src/api/routers/turns.py`, `src/api/schemas/turn_schemas.py`.
2. **WebSocket turns** — For `{"type":"turn", ...}` messages, the server uses `run_id` from the message (or a generated id) as the correlation id for governance and audit on that turn (same router module).
3. **Audit lookup** — `GET /{tenant_id}/admin/audit/events?correlation_id=<id>` returns tenant-scoped rows whose `correlation_id` matches, including ingress decisions (`turn_ingress_decision`), rate-limit and concurrency outcomes where emitted, and tool lifecycle events that reused the same id. Foundation tier; no alternate “shadow” audit path.

**Regression anchors (do not remove without replacement coverage):**

- `tests/modules/api/test_slice3_playground.py` — `test_sse_turn_writes_ingress_allow_decision_audit`, `test_sse_turn_returns_403_when_ingress_gate_denies_empty_input` (audit store queried by the same `correlation_id` passed on the turn).
- `tests/modules/api/test_audit_api.py` — `test_audit_events_and_report_endpoints` (`?correlation_id=` filter on the HTTP audit API).

For optional OTLP/Prometheus export (additive, partial product surface), see §9.2.

### 10.1) Audit Events and Reports (Foundation)

Authoritative row: **Core audit events/report access** (Foundation, **Enforceable**) in [`docs/strategy/entitlement-matrix.md`](../strategy/entitlement-matrix.md).

```
GET  /{tenant_id}/admin/audit/events     # list audit events (filterable)
GET  /{tenant_id}/admin/audit/report     # summary audit report
POST /{tenant_id}/admin/audit/cleanup    # cleanup old events
GET  /{tenant_id}/admin/audit/export     # JSON audit bundle (limit query param; includes chain fingerprint + server signature fields)
```

The **`GET .../export`** response includes `records`, `chain_valid`, `last_record_hash`, `signature_version`, and `signature` (server-computed over the bundle). It uses the same **authenticated** access pattern as events/report in the shipping API (not the Enterprise-only entitlement middleware used by §10.2). **Commercial tier labeling** for this route must stay consistent with your packaging; the matrix explicitly maps the **compliance-grade file export + verify workflow** to **Enterprise** in §10.2 — do not conflate the two rows when making enforceability claims.

**Regression anchors:** `tests/modules/api/test_audit_api.py` (`test_audit_events_and_report_endpoints`, `test_audit_verify_supports_key_rotation_and_legacy_signature_version` uses `GET .../export` to build verify input).

### 10.2) Signed audit file export and verification (Enterprise)

Authoritative row: **Signed audit export and verification workflow** — **Enterprise**, **Enforceable (tier-gated)**, endpoints **`POST /{tenant_id}/admin/audit/export-file`** and **`POST /{tenant_id}/admin/audit/verify`**, with entitlement checks in `src/api/routers/audit.py` and feature key `governance.audit.signed_export_verify` (`EntitledFeature.GOVERNANCE_AUDIT_SIGNED_EXPORT_VERIFY`). Source of truth: [`docs/strategy/entitlement-matrix.md`](../strategy/entitlement-matrix.md).

```
POST /{tenant_id}/admin/audit/export-file       # write signed JSON bundle under the server-managed audit export directory
POST /{tenant_id}/admin/audit/verify            # verify a bundle (inline JSON body and/or `file_path` under that directory)
```

**Behavior**

- **`403`** when the identity lacks Enterprise entitlement: structured error body; an **`entitlement_decision`** audit event is emitted with `surface` **`audit_signed_export_verify`** (see `tests/modules/api/test_audit_api.py` — `test_audit_signed_export_requires_enterprise_entitlement`).
- **Verify** recomputes **chain fingerprint** and validates **signature** server-side; **tenant_id** in the bundle must match the path tenant; tampering fails verification deterministically.

**Regression anchors (do not drop without replacement coverage):**

- `tests/modules/api/test_audit_api.py` — `test_audit_export_file_and_verify_endpoint`, `test_audit_signed_export_requires_enterprise_entitlement`, `test_audit_verify_supports_key_rotation_and_legacy_signature_version`, path-safety tests for export/verify
- `tests/modules/audit/test_evidence_bundle_generation.py`, `tests/modules/audit/test_audit_chain_integrity.py` — chain/signature helpers referenced from the entitlement matrix row

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

This step registers the provider surface for governed execution. Keep provider credentials and provider-native connectivity in your adapter/deployment configuration according to your deployment model.

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

- `docs/strategy/entitlement-matrix.md` — authoritative tier-to-feature mapping
- `docs/strategy/interface-strategy.md` — API-first design rules and safety constraints
- `docs/strategy/governed-execution-positioning.md` — product boundary and customer/deployment ownership model
- `docs/strategy/traceability-matrix.md` — strategy-to-code-to-test anchors
- `src/api/routers/` — canonical endpoint implementations
- `docs/operations/release-candidate-signoff-checklist.md` — release evidence requirements
