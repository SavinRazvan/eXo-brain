<!--
File: northbound-v1-gateway.md
Path: docs/plans/northbound-v1-gateway.md
Role: Design addendum for OpenAI-compatible northbound /v1 surface (Option C next-phase).
Used By:
 - docs/plans/tenant-tool-execution-architecture.md
 - docs/architecture/ARCHITECTURE.md
Depends On:
 - src/api/routers/turns.py
 - src/api/routers/openai_gateway.py
Notes:
 - Advisory design; implementation is feature-flagged until enabled in deployment.
-->

# Northbound OpenAI-compatible `/v1` gateway

## Intent

Expose a **small, OpenAI-shaped** HTTP API so external clients can reuse familiar request bodies, while **all execution** still flows through eXo-brain **tenant runtime**, **ingress gates**, **entitlements**, **rate limits**, and **deterministic tool policy** — same spine as tenant session/turn routes.

This is **not** a transparent reverse proxy to upstream OpenAI; adapters remain **southbound** behind `RuntimeAdapter`.

## Feature flag

- **`EXO_ENABLE_OPENAI_COMPAT_GATEWAY=1`** — registers the `/v1` router from `src/api/app.py`.
- Default **off** — no `/v1` routes in production unless explicitly enabled.

## URL map (MVP)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/v1/chat/completions` | Non-streaming chat completion (subset of OpenAI schema) |

**Not in MVP:** `stream=true` SSE (returns **400** with clear message).

## Auth and tenant binding

| Mechanism | Behavior |
|-----------|----------|
| `Authorization: Bearer`, `X-API-Key`, or (dev/test) `X-Identity` | Same resolution as `src/api/middleware/auth.py` / `get_identity`. |
| Tenant | **`IdentityContext.tenant_id`** — there is no `{tenant_id}` path segment on `/v1`. |
| Session | Required header **`X-eXo-Session-Id`** — must be an existing session created via `/tenants/{tenant_id}/sessions` (same tenant as identity). |

## Middleware / governance order

Aligned with **`POST /tenants/{tenant_id}/sessions/{session_id}/turns`** (SSE):

1. Authenticate → usable identity.
2. Resolve `TenantRuntimeContext` via tenant factory (`get_or_create(tenant_id)`).
3. Verify session exists.
4. **Entitlement** for governance overlay features (`_evaluate_governance_entitlement`).
5. **Ingress** gate chain + budget (`_evaluate_ingress_turn`).
6. Turn **rate limit** and **concurrency** (`run_control_registry`).
7. Stream through **`iter_governed_turn_dicts_for_transport`** → `_stream_turn` → host adapter (same tool/orchestration path as SSE).

## Request mapping

- **User text:** last `messages[]` entry with `role: user` (`content` concatenated as plain text).
- **`model`:** echoed in JSON response; does not override provider selection (session/agent binding unchanged).
- **`user`:** optional correlation id string for audit/debug (defaults to generated id).

## Response mapping (non-streaming)

- **`output_delta` events** → concatenated into `choices[0].message.content`.
- **`run_complete`** → finish `stop`.
- **`error` event** from runtime → **502** with `{"error": {...}}` shaped body (subset of OpenAI error JSON).

## Explicit non-goals

- Raw upstream OpenAI passthrough or API-key forwarding to vendor.
- Bypassing policy, audit, or deterministic tool execution.
- Full OpenAI request/response parity (tools, logprobs, multimodal, streaming).

## References

- Implementation: `src/api/routers/openai_gateway.py`, `src/api/schemas/openai_gateway_schemas.py`
- Shared governance iterator: `iter_governed_turn_dicts_for_transport` in `src/api/routers/turns.py`
- Customer integration: `docs/api/customer-api-integration-guide.md`

## Revision

| Date | Change |
|------|--------|
| 2026-03-24 | Initial addendum + MVP endpoint description. |
