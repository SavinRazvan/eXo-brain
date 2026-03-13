<!--
File: CORE.md
Path: architecture-goals/CORE.md
Role: Deep strategic and architectural guardrails for eXo-brain core layers.
Used By:
 - architecture-goals/GOAL.md
 - architecture-goals/ADAPTER_STRATEGY.md
 - architecture-goals/TRACEABILITY_MATRIX.md
 - docs/modules/core.md
Depends On:
 - src/core/*
 - src/tools/executor.py
 - src/policies/*
 - src/runtime/mode_selector.py
 - src/runtime/runtime_adapter.py
 - src/api/*
Notes:
 - Core decisions here are non-negotiable unless explicitly superseded by a new governance decision.
-->

# Core Strategy and Invariants

## Governance Metadata

- Status: `active`
- Owner: `Savin I. Razvan`
- Version: `1.0.0`
- Last Reviewed: `2026-03-12`
- Review Cadence: `monthly`
- Decision Scope: `Core-layer invariants, responsibility boundaries, and non-bypassable governance model.`

Companion strategy docs:
- `architecture-goals/GOAL.md`
- `architecture-goals/MONETIZATION_STRATEGY.md`
- `architecture-goals/INTERFACE_STRATEGY.md`
- `architecture-goals/TRACEABILITY_MATRIX.md`

## 1) Core Mission

Core is the trust and control plane of eXo-brain.

It must guarantee that:
- provider choice does not change safety posture,
- risky tool calls cannot bypass governance,
- tenant boundaries remain isolated,
- operational evidence is auditable and exportable.

Core is where platform reliability and governance value are created.

---

## 2) Core Outcomes

Core exists to deliver five platform outcomes:

1. Provider-neutral orchestration that survives adapter churn.
2. Deterministic execution for side-effecting/risky operations.
3. Policy-governed decision points before and after tool execution.
4. Multi-tenant fairness and admission control under contention.
5. End-to-end traceability for compliance and incident response.

---

## 3) Non-Negotiable Core Invariants

1. **Provider-neutral orchestration**
   - Core must not branch on provider name.
   - Core consumes capability maps and contracts, never provider SDK internals.

2. **Deterministic-first safety**
   - Risky or state-changing actions must route through deterministic executor.
   - Provider-native fast paths are allowed only when policy and capability gates permit.

3. **Policy wraps all side effects**
   - `before_tool_call` runs before execution.
   - `after_tool_call` runs after execution.
   - Deny/escalate outcomes must be explicit and observable.

4. **Audit continuity**
   - Every governance-relevant decision must be represented in audit evidence.
   - Fallback transitions and cancellations must preserve traceability.

5. **Tenant isolation**
   - Tool, agent, policy, and session state must remain tenant-scoped.
   - Runtime controls must not allow cross-tenant leakage.

6. **Contract stability**
   - Runtime and tool envelopes are versioned contracts.
   - Breaking changes require compatibility strategy, migration path, and test updates.

---

## 4) Core Responsibility Map

## Orchestration (`src/core`)

- Session lifecycle and turn orchestration.
- Background graph execution, scheduling, worker concurrency control.
- Correlation and run state transitions.

## Deterministic Tool Runtime (`src/tools/executor.py`)

- Executes tool calls as deterministic side effects.
- Produces normalized execution envelope and status.

## Policy Layer (`src/policies`)

- Pre-execution allow/deny/escalate decisions.
- Post-execution validation and integrity checks.
- Risk-tier, state-change, and tenant overlay enforcement.

## Runtime Selection (`src/runtime/mode_selector.py`)

- Selects execution mode by capability + policy.
- Prevents unsafe provider-native execution for disallowed contexts.

## Tenancy and Admission (`src/tenancy`, `src/core/run_control_registry.py`)

- Quota/rate/fairness controls and run governance state.
- Enforces bounded operation under load.

## API Contract Surface (`src/api`)

- Exposes tenant/provider/policy/runtime/audit control planes.
- Must not embed orchestration logic that belongs in core.

---

## 5) Core Execution Model

## Turn path

Client input -> API transport -> host adapter -> orchestrator -> runtime adapter -> tool intent -> deterministic executor -> policy checks -> normalized result -> runtime completion -> streamed output/events.

## Background path

Job submit -> quota/admission -> scheduler/task graph -> worker pool -> checkpoint/retry/cancel -> observability and run-control APIs.

Design target:
- both paths share policy, audit, and deterministic guarantees.

---

## 6) Safety and Failure Model

## Required safety behavior

- Deny unsafe tool calls with explicit reason codes.
- Preserve idempotent cancellation where feasible.
- Normalize provider errors into platform error envelopes.
- Prevent log leakage of secrets and sensitive payloads.
- Keep fallback from degrading safety posture.

## Failure handling priorities

1. Protect invariants (safety/governance) before throughput.
2. Fail closed for ambiguous high-risk tool operations.
3. Emit operationally useful telemetry for diagnosis and replay.

---

## 7) Core Extension Points (Allowed)

- Runtime adapters implementing the stable contract.
- Tool plugins registered through governed interfaces.
- Policy overlays and risk profiles configured via API.
- Provider capability metadata and fallback chains configured by tenants.

## Forbidden shortcuts

- Provider SDK imports in core.
- Direct side-effect execution in adapter path for risky calls.
- Controller/router logic that bypasses policy middleware.
- Cross-tenant mutable global state without explicit governance.

---

## 8) Core SLO and Reliability Direction

Core should optimize for:
- low p95 turn latency under policy-governed operation,
- bounded queue wait times under contention,
- low timeout and failure amplification rates,
- deterministic behavior under retry/cancel races.

Performance improvements must not weaken governance checks.

---

## 9) Core Monetization Boundary

Core is the premium surface for:
- policy packs and governance profiles,
- advanced runtime controls and admission policies,
- signed audit evidence and compliance workflows,
- reliability and fairness guarantees at scale.

Adapter connectivity enables adoption; core governance creates durable revenue value.

---

## 10) Change Governance for Core

Any core-impacting change must include:
- explicit contract impact assessment,
- invariant compatibility check,
- updated test coverage for happy/failure/cancel paths,
- updated traceability mapping in `architecture-goals/TRACEABILITY_MATRIX.md`.

If a change weakens invariants, it must not merge without explicit redesign or accepted divergence rationale.

---

## 11) Core Open Risks

1. **Contract drift across adapters**
   - Mitigation: strict certification and compatibility matrix.
2. **Policy latency inflation on hot paths**
   - Mitigation: keep checks fast and local, avoid blocking DB calls in hot loop.
3. **Fallback complexity under mixed providers**
   - Mitigation: capability + policy-driven deterministic fallback planner.
4. **Operational blind spots**
   - Mitigation: mandatory correlation IDs and run/audit evidence checks.

---

## 12) Core Alignment Checklist

- Does this preserve provider-neutral orchestration?
- Does deterministic enforcement still protect risky paths?
- Are policy hooks guaranteed around side effects?
- Is tenant isolation maintained in state and APIs?
- Can this be traced, exported, and verified operationally?

If any answer is "no", stop implementation and redesign.
