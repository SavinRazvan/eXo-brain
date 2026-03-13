<!--
File: GOAL.md
Path: architecture-goals/GOAL.md
Role: Product, architecture, and monetization north-star for eXo-brain.
Used By:
 - architecture-goals/ADAPTER_STRATEGY.md
 - README.md
 - AGENTS.md
 - docs/plans/tenant-tool-execution-architecture.md
Depends On:
 - src/core/*
 - src/runtime/*
 - src/tools/*
 - src/policies/*
 - src/api/*
Notes:
 - Keep aligned with API-first Option C delivery.
 - Update when package boundaries, business model, or governance model changes.
-->

# eXo-brain Goal and Strategic Alignment

## Governance Metadata

- Status: `active`
- Owner: `Savin I. Razvan`
- Version: `1.0.0`
- Last Reviewed: `2026-03-12`
- Review Cadence: `monthly`
- Decision Scope: `Product north-star, strategic boundaries, and long-term direction for provider-neutral orchestration.`

## 1) Why this file exists

This file defines the long-term purpose of eXo-brain so architecture, packaging, and business decisions stay aligned.

It is the reference for:
- what problems we solve,
- where the product boundary is,
- how core and adapters are separated,
- how monetization works without weakening safety/governance.

Companion strategy docs:
- `architecture-goals/README.md`
- `architecture-goals/CORE.md`
- `architecture-goals/ADAPTER_STRATEGY.md`
- `architecture-goals/MONETIZATION_STRATEGY.md`
- `architecture-goals/ENTITLEMENT_MATRIX.md`
- `architecture-goals/COMPLIANCE_PROFILE_MATRIX.md`
- `architecture-goals/DEPLOYMENT_MODELS.md`
- `architecture-goals/INTERFACE_STRATEGY.md`
- `architecture-goals/TRACEABILITY_MATRIX.md`

---

## 2) Product purpose

eXo-brain is a provider-neutral AI orchestration platform where:
- providers are replaceable adapters,
- deterministic execution is mandatory for risky/state-changing operations,
- policy and audit controls are first-class,
- customers consume all controls and telemetry through API.

In simple terms:
- adapters give model connectivity,
- core gives trust, control, and enterprise reliability.

---

## 3) Problems we solve

### A. Provider lock-in and migration pain
- Teams can switch providers without rewriting orchestration logic.
- Runtime selection is contract/capability/policy driven, not provider-name hardcoded.

### B. Unsafe tool execution
- High-impact tool calls are executed through deterministic runtime and policy gates.
- Model tool intent is separated from side-effect execution.

### C. Lack of policy control
- Customers can define per-tenant overlays (deny/escalate/allow behavior).
- Risk gates and governance controls can be changed without redeploying core logic.

### D. Missing traceability and compliance evidence
- Tool calls, outcomes, and policy decisions are auditable.
- Audit export and verification are available via API.

### E. Multi-tenant scale issues
- Tenant-scoped isolation, quotas, rate limits, and fairness controls exist by design.
- Control-plane state can be shared/durable for consistent admission behavior.

---

## 4) Core product boundary

### In scope (our product value)
- Provider-neutral orchestration contracts.
- Deterministic-first tool execution.
- Policy middleware and risk gates.
- Tenant isolation, rate limits, quotas, fairness.
- Audit logging, export, verification, and operational controls.
- API layer for integration into customer UI/platforms.

### Out of scope (customer-owned or adapter-owned)
- Customer business workflows and domain data schemas.
- Customer-specific front-end/dashboard UX as a required product surface in the current delivery scope.
- Provider proprietary SDK lifecycle decisions inside customer products.

UI scope note:
- UI is out of current delivery scope; optional API-driven console may be added later.

---

## 5) Three-part architecture model

## Part 1: Core (control plane and governance plane)

Core must remain provider-neutral and own:
- orchestration,
- policy gates,
- deterministic tool execution,
- tenant governance,
- observability and audit.

Core is the non-bypassable enforcement layer.

## Part 2: Adapter SDK (developer kit for adapters)

Adapter SDK must provide:
- stable runtime contracts,
- conformance checks,
- helper interfaces for adapter authors.

SDK reduces adapter quality variance and protects core compatibility.

## Part 3: Provider adapters (pluggable data plane connectors)

Each provider adapter should:
- implement runtime transport/provider specifics,
- publish capability map,
- follow contract and conformance rules,
- avoid embedding governance logic that belongs in core.

Initial adapter target set:
- OpenAI
- Google Gemini
- Anthropic
- xAI (Grok)
- Meta (Llama endpoints)

Recommended package naming:
- `exo-adapter-openai`
- `exo-adapter-google-gemini`
- `exo-adapter-anthropic`
- `exo-adapter-xai`
- `exo-adapter-meta-llama`

---

## 6) Adapter separation rules (do not violate)

1. No provider SDK imports in core modules.
2. No adapter path may bypass policy middleware for state-changing calls.
3. No adapter path may bypass deterministic execution when policy/risk requires it.
4. Core owns policy decisions, audit records, and compliance envelopes.
5. Adapters expose capabilities and transport behavior, not governance authority.
6. Capability + policy drive mode selection, never provider-name branching in core orchestration.

---

## 7) Customer configuration model

Customers should be able to configure through API:
- provider registration and selection,
- agent routing and fallback behavior,
- policy overlays (deny/escalate rules),
- risk tiers and execution mode constraints,
- quotas, rate limits, and fairness limits,
- runtime controls and cancellation,
- audit query/export/verification.

This gives customers control while preserving core invariants.

---

## 8) Monetization model

Monetization should focus on governance and operational value, not raw model access.

### Revenue pillars
- Governance controls (policy packs, risk templates, approval flows).
- Compliance and audit artifacts (signed export, verification workflows).
- Reliability and scale controls (fairness, SLO gates, non-blocking orchestration).
- Enterprise operations (multi-tenant controls, runtime admin APIs, BYOC hardening).
- Premium observability (advanced dashboards and anomaly detection using existing APIs).

### Example tiering
- Community/Foundation:
  - core runtime baseline,
  - basic adapter support,
  - basic deterministic and policy controls.
- Pro:
  - advanced policy templates,
  - richer operational APIs,
  - stronger observability and governance reports.
- Enterprise:
  - full compliance packs,
  - signed evidence workflows,
  - advanced tenancy and fairness controls,
  - SLO-gated release operations and support features.

---

## 9) How to keep this safe and avoid breaking core

### Contract governance
- Version contracts with strict compatibility policy.
- Require adapter conformance checks before acceptance.
- Maintain explicit capability maps for each adapter.

### Runtime safety
- Keep deterministic path mandatory for risky/state-changing operations.
- Keep policy `before_tool_call` and `after_tool_call` around every side-effect path.
- Keep adapter failures isolated and recoverable (fallbacks, retries, cancellation controls).

### Release safety
- Gate with tests + architecture checks + release signoff evidence.
- Add adapter certification checklist before publishing adapter versions.
- Use staged rollout strategy for new adapters and major changes.

---

## 10) Integration model for customer projects/cloud

Target usage pattern:
1. Customer deploys eXo-brain API.
2. Customer installs selected adapters.
3. Customer registers providers, tools, agents, and policies via API.
4. Customer builds their own UI/platform on top of eXo-brain APIs.
5. Customer uses audit and runtime endpoints for governance and observability.

This keeps eXo-brain as the secure orchestration backbone.

---

## 11) Current gap to close for fully portable adapters

Adapter packages must be fully standalone and not depend on monorepo-only imports.

Required outcome:
- core contracts and adapter SDK are externalizable and stable,
- each provider adapter can be installed in a separate project and still pass conformance.

---

## 12) Success metrics

### Product metrics
- Time to add/swap provider adapter.
- Percentage of tool calls executed under deterministic governance.
- Policy violation prevention rate.
- Audit export/verify success rate.
- Tenant fairness and queue wait SLO adherence.

### Business metrics
- Paid tenants using policy/audit/governance features.
- Adapter ecosystem growth and certified adapter count.
- Expansion revenue from Pro/Enterprise governance capabilities.

---

## 13) Alignment checklist before major implementation slices

- Does this change preserve provider-neutral core boundaries?
- Can a customer configure it via API without code patching core?
- Does policy middleware still wrap all side-effect paths?
- Is deterministic execution still enforced for risky/state-changing calls?
- Are audit and observability events complete and verifiable?
- Is the change compatible with adapter contract version policy?

If any answer is "no", stop and redesign before merging.

---

## 14) Practical next alignment steps

1. Finalize external package boundaries for adapter portability.
2. Define adapter certification matrix for the five target providers.
3. Publish a customer-facing API integration guide focused on policy/audit operations.
4. Add monetization-oriented feature flags and entitlement hooks around governance surfaces.
5. Keep this file synchronized with `README.md`, `AGENTS.md`, canonical architecture docs, and `architecture-goals/ADAPTER_STRATEGY.md`.
