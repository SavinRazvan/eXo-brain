<!--
File: INTERFACE_STRATEGY.md
Path: architecture-goals/INTERFACE_STRATEGY.md
Role: Interface strategy for API-first operation, platform integrations, and future UI roadmap constraints.
Used By:
 - architecture-goals/GOAL.md
 - architecture-goals/CORE.md
 - architecture-goals/TRACEABILITY_MATRIX.md
 - docs/operations/release-candidate-signoff-checklist.md
Depends On:
 - src/api/app.py
 - src/api/routers/*
 - src/api/schemas/*
 - src/runtime/tenant_runtime.py
Notes:
 - Current canonical posture is API-first; UI/dashboard tracks are optional and deferred unless explicitly re-enabled.
-->

# Interface Strategy

## Governance Metadata

- Status: `active`
- Owner: `Savin I. Razvan`
- Version: `1.1.0`
- Last Reviewed: `2026-03-14`
- Review Cadence: `monthly`
- Decision Scope: `API-first interface posture, UI roadmap constraints, and interface-level governance rules.`

Companion strategy docs:
- `architecture-goals/GOAL.md`
- `architecture-goals/MONETIZATION_STRATEGY.md`
- `architecture-goals/COMPLIANCE_PROFILE_MATRIX.md`
- `architecture-goals/DEPLOYMENT_MODELS.md`
- `architecture-goals/TRACEABILITY_MATRIX.md`

## 1) Purpose

Define how users and customer platforms interact with eXo-brain safely and consistently.

This strategy clarifies:
- API-first operation today,
- what UI may do when introduced,
- what must remain backend-enforced regardless of interface.

---

## 2) Current Interface Posture

Current canonical mode:
- API-first (REST + SSE + WebSocket).
- No required backend-served UI/dashboard for core operation.
- UI is out of current delivery scope; optional API-driven console may be added later.

Implication:
- customer products can build their own UI and consume all control/observability via API.

---

## 3) Interface Layers and Roles

## Layer A: Public API (authoritative control plane)

Responsibilities:
- provider management,
- tenant policy and quota control,
- tenant ingress safety profile and gate/policy control,
- tool and agent lifecycle,
- turn execution and streaming,
- runtime control operations,
- audit reporting/export/verification.

## Layer B: Customer UI/Platform (consumer of APIs)

Responsibilities:
- tenant-specific UX and workflows,
- visualization and decision support,
- user-facing governance workflows.

Constraint:
- UI cannot be trust boundary; all safety checks remain backend-enforced.

---

## 4) API-First Design Rules

1. Every critical operation must be available via API first.
2. UI-only business logic must not become the source of truth.
3. API envelopes and contracts are versioned and documented.
4. Streaming semantics (SSE/WS) must be deterministic and observable.
5. Any UI capability must map to an existing or planned API endpoint.
6. Turn execution must pass through server-side ingress safety decisions before orchestration/runtime execution.

---

## 5) UI Strategy (Deferred Optional Surface)

If UI is introduced or re-enabled later, it should be:
- thin orchestration client over APIs,
- role-aware interface for governance and runtime operations,
- observability-focused (runs, tool calls, policy decisions, audit reports),
- safe by construction (no bypass paths).

Recommended UI domains:
- Tool Manager
- Agent Manager
- Session/Playground
- Runtime Control
- Audit and Compliance dashboard
- Tenant Governance panel

---

## 6) Interface Safety Constraints

Non-negotiable controls:
- identity and access control enforced server-side,
- policy middleware and deterministic runtime enforced server-side,
- audit evidence generated server-side,
- tenant boundaries enforced server-side.

No interface (CLI/UI/SDK) may bypass these controls.

---

## 7) API Contract Principles

- Prefer typed request/response schemas and stable event envelopes.
- Expose reason codes for denies/escalations/fallback transitions.
- Keep operational introspection endpoints for debugging and governance.
- Version breaking changes and provide migration guidance.

---

## 8) Streaming Interaction Model

SSE and WS should both communicate:
- ingress safety decision and reason-code outcomes when relevant,
- output deltas,
- tool call and progress lifecycle,
- tool result envelopes,
- run completion or cancellation.

Design goal:
- equivalent governance and observability guarantees across SSE and WS paths.

---

## 9) Governance Ingress API Model

Governance ingress should be exposed as API-first controls:
- predefined gate/policy profiles (safe/balanced/strict),
- tenant custom declarative gate rules and protocol constraints,
- optional specialized classifier gates (tier-dependent),
- explicit fail-safe and latency budget controls per profile.

Decision contract requirements:
- `allow|deny|escalate` outcomes with stable reason codes,
- correlation-linked decision evidence in audit stream,
- no hidden bypass path from transport to orchestration.

---

## 10) Customer Integration Patterns

Primary pattern:
1. Customer backend integrates with eXo-brain APIs.
2. Customer UI reads/writes through customer backend or directly via secure API gateway.
3. Governance and audit workflows are driven by API responses and events.

Secondary pattern:
- internal operations teams consume runtime/audit APIs for incident response and compliance.

---

## 11) Interface and Monetization Alignment

Interface strategy should support monetization by exposing premium governance features via API:
- advanced policy and risk configuration,
- advanced ingress gate configuration and custom policy packs,
- audit export/verification workflows,
- runtime/fairness governance controls,
- enterprise reliability and compliance operations.

Rule:
- premium features are expanded controls and evidence depth, not safety bypasses.

---

## 12) Operational Quality Gates for Interfaces

Before shipping interface changes:
- contract and schema validation updates,
- SSE/WS behavior verification,
- authz and tenant boundary tests,
- ingress gate latency budget and failure-mode verification,
- documentation and runbook updates,
- release-candidate signoff evidence updates.

---

## 13) Open Questions

1. Should future UI be separate deployable product or optional module?
2. Which workflows require guided UX first (Tool Manager, Audit, Runtime Control)?
3. What minimum API stability guarantees are needed for customer platform integrations?
4. Which interface analytics are required for monetization conversion optimization?
5. Which ingress-gate controls should remain Foundation baseline vs Pro/Enterprise depth?
6. What p95 ingress-latency budget is acceptable per deployment profile?

---

## 14) Decision Checklist

- Does this preserve API-first canonical operation?
- Does it avoid UI becoming a trust boundary?
- Are safety and governance controls server-enforced?
- Are ingress safety decisions observable and non-bypassable across SSE/WS/HTTP?
- Is the contract clear enough for customer platform integration?
- Does it improve observability and governance usability?

If any answer is "no", redesign before implementation.
