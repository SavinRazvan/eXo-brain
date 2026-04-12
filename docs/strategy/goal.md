<!--
File: goal.md
Path: goal.md
Role: Product, architecture, and monetization north-star for eXo-brain.
Used By:
 - adapter-strategy.md
 - next-directions.md
 - execution-board-12-gaps.md
 - README.md
 - AGENTS.md
 - docs/plans/tenant-tool-execution-architecture.md
 - docs/plans/short-long-term-execution-plan.md
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
- Version: `1.8.0`
- Last Reviewed: `2026-04-01`
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
- `README.md`
- `core.md`
- `adapter-strategy.md`
- `monetization-strategy.md`
- `entitlement-matrix.md`
- `compliance-profile-matrix.md`
- `deployment-models.md`
- `interface-strategy.md`
- `traceability-matrix.md`
- `next-directions.md`
- `execution-board-12-gaps.md`
- `customer-self-serve-governance-journey.md`
- `foundation-tier-adoption-checklist.md`

---

## 2) Product purpose

eXo-brain is a provider-neutral AI orchestration platform where:
- providers are replaceable adapters,
- customers keep provider/model connectivity in adapters and deployment environments they control,
- deterministic execution is mandatory for risky/state-changing operations,
- policy and audit controls are first-class,
- customers consume governed execution controls through API,
- enterprise operations can consume standard telemetry exports through supported deployment profiles.

In simple terms:
- adapters give model connectivity,
- core gives trust, control, and enterprise reliability as the governed execution boundary.

### North star (mission, qualified)

As AI becomes **infrastructure** inside products, teams need a **repeatable governed boundary** — policy, deterministic tools, audit, entitlements — without re-implementing it for every provider and every launch. eXo-brain targets that layer: **monetize governance and operational assurance**, keep **provider connectivity neutral and versioned**, and let **customer applications** attach through the **control plane API** and **customer bridge** patterns (see `governed-execution-positioning.md`: four-layer separation of concerns and integration surfaces). Claims in sales and docs must stay **evidence-aligned** with current platform maturity.

### Repository scope (control plane only)

The **primary codebase** for this product is the **control plane** (API, core, policies, tools, tenancy, audit). **Adapter SDK**, **published contracts**, and **provider adapter packages** are **separate deliverables** in **other repositories** — not a long-term monorepo beside the control plane. Any in-tree `packages/` is **transitional** until extraction completes (`governed-execution-positioning.md`, **Repository boundary**).

---

## 3) Problems we solve

### A. Provider lock-in and migration pain
- Teams can switch providers without rewriting orchestration logic.
- Runtime selection is contract/capability/policy driven, not provider-name hardcoded.

### B. Unsafe tool execution
- High-impact tool calls are executed through deterministic runtime and policy gates.
- Model tool intent is separated from side-effect execution.

### C. Lack of policy control
- Customers can choose predefined governance profiles and per-tenant overlays (deny/escalate/allow behavior).
- Customers can add bounded custom policy/gate rules without redeploying core logic.
- High-flexibility customization (plugin-style custom gates) must remain sandboxed, signed, and policy-governed.

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
- Standard telemetry export posture for supported enterprise operations.
- API layer for integration into customer UI/platforms.

### Out of scope (customer-owned or adapter-owned)
- Customer business workflows and domain data schemas.
- Customer-specific front-end/dashboard UX as a required product surface in the current delivery scope.
- Provider proprietary SDK lifecycle decisions inside customer products.
- Provider credentials, provider-native account setup, and cloud/network ownership for customer-controlled adapters.

UI scope note:
- UI is out of current delivery scope; optional API-driven console may be added later.

---

## 5) Three-part architecture model

## Part 1: Core (control plane and governance plane)

Core must remain provider-neutral and own:
- orchestration,
- ingress safety gating before model/runtime execution,
- policy gates,
- deterministic tool execution,
- tenant governance,
- observability and audit,
- standard telemetry export contracts for supported deployment profiles.

Core is the non-bypassable enforcement layer.

## 5a) Customer integration surfaces (control plane in the loop)

§5 describes **internal platform layers** (core, adapter SDK, provider packages). This section names how **customers** attach eXo-brain to **their** organizations and end-user applications — complementary to §10.

| Surface | Meaning |
|---------|---------|
| **Provider runtime adapter** | Outbound from the hosted runtime to a model/provider, via versioned packages and contracts; keeps orchestration **provider-neutral**. |
| **Control plane API** | Authoritative REST/SSE/WS surface for governed execution, policy, audit, tools, agents, tenants, and provider registration. |
| **Customer bridge** | Customer app integration: direct API use today; optional OpenAI-compatible **`/v1`** ingress (feature flag); **planned** thin SDK with **parity** to HTTP governance (no bypass). |

**BYOC / worker connectors** follow dedicated runtime plans; they remain subject to the same policy and deterministic execution invariants.

Canonical narrative: `governed-execution-positioning.md` and [`docs/plans/control-plane-product-alignment-plan.md`](../plans/control-plane-product-alignment-plan.md).

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

Initial adapter baseline set:
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

Planned expansion set (Adapter Portfolio Expansion v2):
- Hugging Face (hybrid compatible -> native path)
- Mistral
- DeepL (service/tool lane)
- Aleph Alpha
- MiniMax
- Moonshot
- Zhipu
- DeepSeek
- Qwen
- Minerva (discovery)
- Velvet (discovery)

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
- predefined policy/gate profiles and policy overlays (deny/escalate rules),
- custom declarative gate rules and protocol checks (tier-dependent),
- optional specialized low-cost classifier gates for ingress safety (tier-dependent),
- risk tiers and execution mode constraints,
- quotas, rate limits, and fairness limits,
- runtime controls and cancellation,
- audit query/export/verification.

This gives customers control while preserving core invariants.

### 7a) Customer self-serve governance (product contract)

Customers must be able to **drive their own governance** for adapter-backed workflows **through the control plane API**:

- configure gates, guardrails, policy overlays, tool/agent registration, provider registration, and quotas within **tenant scope**;
- **iterate safely** using observable outcomes (reason codes, audit events, `correlation_id` joins) and patterns in [`docs/api/governance-preview-and-testing.md`](../api/governance-preview-and-testing.md);
- rely on a **single configuration spine**: any future forms or dashboard modules are **thin clients** over the same APIs (no parallel config model) — see [`docs/strategy/interface-strategy.md`](interface-strategy.md) and [`docs/plans/governance-configuration-reference-model.md`](../plans/governance-configuration-reference-model.md).

**Canonical narrative and scope checklist:** [`docs/strategy/customer-self-serve-governance-journey.md`](customer-self-serve-governance-journey.md). **Foundation minimum path:** [`docs/strategy/foundation-tier-adoption-checklist.md`](foundation-tier-adoption-checklist.md).

**Commercial posture vs technical self-serve:** API-driven configuration is the **default product mechanics**; broad **enterprise commercial claims** remain evidence-gated per [`docs/strategy/monetization-strategy.md`](monetization-strategy.md) §10–§10a.

---

## 8) Monetization model

Monetization should focus on governance and operational value, not raw model access.

### Revenue pillars
- Governance controls (policy packs, gate templates, risk templates, approval flows).
- Compliance and audit artifacts (signed export, verification workflows).
- Reliability and scale controls (fairness, SLO gates, non-blocking orchestration).
- Enterprise operations (multi-tenant controls, runtime admin APIs, BYOC hardening).
- Premium observability and telemetry interoperability (advanced dashboards, anomaly detection, and standard telemetry export using existing APIs and supported sinks).

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
- Keep turn-ingress gate evaluation bounded by explicit latency budgets and fail-safe behavior.
- Keep adapter failures isolated and recoverable (fallbacks, retries, cancellation controls).

### Release safety
- Gate with tests + architecture checks + release signoff evidence.
- Add adapter certification checklist before publishing adapter versions.
- Use staged rollout strategy for new adapters and major changes.

---

## 10) Integration model for customer projects/cloud

Target usage pattern:
1. Customer deploys eXo-brain API (**control plane**).
2. Customer installs **provider runtime adapters** and keeps provider credentials/configuration in customer-controlled environments (Surface A).
3. Customer registers providers, tools, agents, and policies via **control plane API** (Surface B).
4. Customer applications use Surface B and/or **customer bridge** options (optional `/v1` OpenAI-shaped ingress; future thin SDK) so governed execution sits **in their AI loop** under subscription scope.
5. Customer builds their own UI/platform on top of eXo-brain APIs where desired.
6. Customer uses audit and runtime endpoints for governance and observability.
7. Customer exports operational telemetry through supported sinks such as OpenTelemetry/Prometheus when those deployment profiles are enabled.

This keeps eXo-brain as the governed execution backbone without turning it into a raw model-access resale surface. **Monetization attaches to governance and assurance** (policy, audit, deterministic tools, entitlements), not to commodity provider transport alone.

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

Canonical source: `next-directions.md`. **Horizon split (short vs long term, main UI as API consumer):** `docs/plans/short-long-term-execution-plan.md`.

Summary:
1. Finalize external package boundaries for adapter portability.
2. Define and enforce adapter certification matrix for the baseline and expansion portfolio.
3. Introduce a governance ingress plane for pre-model allow/deny/escalate decisions.
4. Publish a customer-facing API integration guide focused on policy/audit/governance operations.
5. Add monetization-oriented feature flags and entitlement hooks around governance surfaces.
6. Keep this file synchronized with `README.md`, `AGENTS.md`, canonical architecture docs, `adapter-strategy.md`, and `next-directions.md`.
7. Near term: **pilot-complete core** for a reference workflow; **governance + observability + audit** provable via APIs for integrators (including a **separate main UI platform** — `interface-strategy.md` Layer B); **adapter SDK** with **OpenAI** as the first reference adapter path (`short-long-term-execution-plan.md`).
