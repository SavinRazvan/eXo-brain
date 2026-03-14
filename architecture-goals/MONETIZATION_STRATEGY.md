<!--
File: MONETIZATION_STRATEGY.md
Path: architecture-goals/MONETIZATION_STRATEGY.md
Role: Monetization strategy for eXo-brain aligned with provider-neutral architecture and governance-first value.
Used By:
 - architecture-goals/GOAL.md
 - architecture-goals/CORE.md
 - architecture-goals/ADAPTER_STRATEGY.md
 - architecture-goals/ENTITLEMENT_MATRIX.md
 - architecture-goals/COMPLIANCE_PROFILE_MATRIX.md
 - architecture-goals/DEPLOYMENT_MODELS.md
 - architecture-goals/TRACEABILITY_MATRIX.md
Depends On:
 - src/policies/*
 - src/audit/*
 - src/tenancy/*
 - src/api/routers/*
 - scripts/release/*
Notes:
 - Revenue should attach to governance, reliability, and compliance surfaces.
-->

# Monetization Strategy

## Governance Metadata

- Status: `active`
- Owner: `Savin I. Razvan`
- Version: `1.1.0`
- Last Reviewed: `2026-03-14`
- Review Cadence: `monthly`
- Decision Scope: `Tier strategy, entitlement boundaries, and value-capture model for governance-first monetization.`

Companion enforcement docs:
- `architecture-goals/ENTITLEMENT_MATRIX.md`
- `architecture-goals/COMPLIANCE_PROFILE_MATRIX.md`
- `architecture-goals/DEPLOYMENT_MODELS.md`
- `architecture-goals/TRACEABILITY_MATRIX.md`

## 1) Monetization Thesis

Do not monetize raw provider connectivity alone.

Monetize:
- safety guarantees,
- governance controls,
- compliance evidence,
- operational reliability at multi-tenant scale.

Adapters are adoption drivers; governance and reliability are durable revenue drivers.

---

## 2) Value Capture Model

## Commodity layer (low margin)

- provider API transport and base model invocation,
- basic adapter connectivity.

## High-value layer (high margin)

- deterministic side-effect safety,
- policy/risk gate frameworks,
- turn-ingress safety gate chains (predefined and custom),
- audit export/verification workflows,
- fairness/admission and runtime controls,
- SLO-governed operations.

Goal:
- keep adapter onboarding easy,
- keep governance and reliability differentiated.

---

## 3) Product Tiers (Proposed)

## Foundation

Target users:
- builders validating flows and small teams.

Includes:
- provider-neutral orchestration baseline,
- basic adapter registration and selection,
- baseline deterministic policy path,
- baseline ingress safety profiles and protocol checks,
- standard observability and core API surface.

## Pro

Target users:
- production teams with governance and reliability requirements.

Adds:
- advanced policy templates, risk profiles, and gate packs,
- tenant custom declarative gate rules and protocol policies,
- low-cost specialized classifier gates and shadow-mode evaluation,
- richer fallback and route controls,
- expanded runtime diagnostics and administrative controls,
- stronger tenant-level governance automation.

## Enterprise

Target users:
- regulated/high-scale organizations.

Adds:
- signed and verifiable audit evidence workflows,
- signed/custom governance plugin packs with strict sandbox controls,
- advanced tenancy/fairness and admission controls,
- release-gated compliance evidence bundles,
- premium operational assurance and support capabilities.

---

## 4) Feature-to-Tier Boundary Rules

Use these rules to avoid confusion:

1. Features required for platform trust baseline remain available at Foundation.
2. Features that automate or scale governance become Pro/Enterprise.
3. Compliance-grade artifact workflows and strict controls are Enterprise.
4. Adapters remain broadly available to preserve provider-neutral adoption.

---

## 5) Entitlement and Packaging Strategy

Entitlements should be enforced at API/config boundaries, not hidden in adapter internals.

Recommended entitlement categories:
- ingress safety profile depth,
- custom gate/policy capability depth,
- specialized model gate usage and shadow-mode controls,
- policy profile depth,
- audit export/sign/verify workflows,
- runtime control depth,
- fairness/admission advanced options,
- governance analytics depth.

Implementation principle:
- entitlement checks should be explicit, observable, and testable.

---

## 6) Revenue Metrics and Leading Indicators

## Adoption metrics

- active tenants using multiple adapters,
- adapter swap/fallback usage frequency,
- API integration activation rates.

## Governance usage metrics

- percentage of tenants with active policy overlays,
- percentage of turns evaluated by ingress gate chain,
- deny/escalate rate by gate profile and tenant segment,
- deterministic execution coverage on side-effect calls,
- audit export/verify workflow usage.

## Reliability metrics

- p95 turn latency under policy load,
- p95 ingress gate latency and timeout rate,
- queue wait budget adherence,
- timeout/error/retry amplification trends.

## Commercial metrics

- Foundation -> Pro conversion rate,
- Pro -> Enterprise expansion rate,
- net revenue retention from governance-heavy tenants.

---

## 7) Pricing Motion (Non-Numeric Framework)

Recommend blended model:
- platform subscription by tier,
- usage dimensions tied to tenant scale and governance workload,
- add-on packages for enterprise governance/compliance features.

Avoid billing model that incentivizes bypassing deterministic safety path.

---

## 8) Sales Narrative Anchors

Primary narrative:
- "Bring any provider, keep one governance and reliability model."

Secondary anchors:
- "Switch providers without rewriting orchestration."
- "Enforce policy before side effects."
- "Produce audit evidence by API, not manual operations."
- "Scale tenants with fairness and controls, not best-effort chaos."

---

## 9) Monetization Risks and Mitigations

1. **Risk: Over-gating core trust features**
   - Mitigation: keep safety baseline in Foundation.

2. **Risk: Adapters treated as premium lock-in**
   - Mitigation: keep adapters open and contract-driven.

3. **Risk: Tier confusion**
   - Mitigation: publish explicit feature boundary matrix and entitlement tests.

4. **Risk: Governance overhead slows adoption**
   - Mitigation: provide progressive profiles (baseline -> strict) with safe defaults.

5. **Risk: Safety gate latency harms user experience**
   - Mitigation: enforce per-gate latency budgets, tiered gate ladders (rules first), and explicit fail-safe modes.

---

## 10) Alignment with Core and Adapter Strategy

Monetization must not violate architecture:
- no premium shortcut that bypasses policy/deterministic guards,
- no adapter-specific private bypass inside core,
- no paid feature that weakens tenant isolation or audit guarantees.

Premium value should reinforce, not compromise, platform invariants.

---

## 11) Execution Plan (Business + Engineering)

1. Define entitlement matrix for Foundation/Pro/Enterprise.
2. Define governance ingress product model (profiles, custom rules, optional plugin packs, performance SLOs).
3. Bind entitlement checks to explicit API/config control points.
4. Add entitlement + gate-decision observability in audit and runtime admin endpoints.
5. Publish feature boundary documentation and onboarding playbooks.
6. Review quarterly against adoption, governance usage, and retention metrics.

---

## 12) Decision Checklist

- Does this monetization decision preserve core trust guarantees?
- Does it keep provider neutrality intact?
- Is entitlement enforcement explicit and testable?
- Does the pricing boundary align with actual customer value?
- Does this improve long-term retention rather than short-term lock-in?

If any answer is "no", revise before rollout.
