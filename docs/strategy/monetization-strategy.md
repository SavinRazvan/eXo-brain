<!--
File: MONETIZATION_STRATEGY.md
Path: monetization-strategy.md
Role: Monetization strategy for eXo-brain aligned with provider-neutral architecture and governance-first value.
Used By:
 - goal.md
 - core.md
 - adapter-strategy.md
 - entitlement-matrix.md
 - compliance-profile-matrix.md
 - deployment-models.md
 - traceability-matrix.md
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
- Version: `1.4.0`
- Last Reviewed: `2026-04-01`
- Review Cadence: `monthly`
- Decision Scope: `Tier strategy, entitlement boundaries, and value-capture model for governance-first monetization.`

Companion enforcement docs:
- `governed-execution-positioning.md`
- `customer-self-serve-governance-journey.md`
- `entitlement-matrix.md`
- `compliance-profile-matrix.md`
- `deployment-models.md`
- `traceability-matrix.md`

## 1) Monetization Thesis

eXo-brain is not a model reseller and not a generic LLM wrapper.

**Control plane framing:** the paid product is the **governed execution and safety boundary** — policy, ingress gates, deterministic tool execution, audit evidence, entitlements, runtime control, and tenant governance — delivered primarily through the **control plane API** (with optional **customer bridge** surfaces for integration ergonomics). Provider runtime adapters enable customer-owned model connectivity but are **not** the primary margin story.

eXo-brain should be sold as the governed execution boundary for tool-using AI systems:

- customers keep their own model and provider connectivity,
- eXo-brain governs risky or state-changing actions,
- durable paid value comes from policy, deterministic execution, audit, and runtime control.

Do not monetize raw provider connectivity alone.

Monetize:
- non-bypassable execution safety,
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

Boundary rule:
- provider credentials, provider-native settings, and customer business workflows remain customer-owned,
- governance, deterministic execution, audit, runtime control, and entitlements remain eXo-brain-owned,
- avoid split-brain configuration by keeping one source of truth per concern.

---

## 3) Ideal Customer and Best Initial Use Cases

## Best-fit buyers

- B2B SaaS teams embedding AI into workflows with real tool side effects,
- internal AI platform teams that need one governance model across providers,
- security/compliance-sensitive teams that need auditability and operational control,
- teams expecting provider churn, fallback requirements, or multi-provider strategy.

## Weak-fit buyers

- hobby builders,
- simple single-provider chat applications,
- prompt-only or playground-only use cases,
- teams without risky tool execution or compliance pressure.

## Best first use cases

- CRM or ticket mutations,
- internal operations automation,
- support workflow automation,
- approval-heavy business processes,
- agent-assisted flows that call internal APIs, databases, or privileged tools.

These use cases create the clearest willingness to pay for deterministic control, policy gates, and audit trails.

---

## 4) Product Tiers (Proposed)

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

## 5) Feature-to-Tier Boundary Rules

Use these rules to avoid confusion:

1. Features required for platform trust baseline remain available at Foundation.
2. Features that automate or scale governance become Pro/Enterprise.
3. Compliance-grade artifact workflows and strict controls are Enterprise.
4. Adapters remain broadly available to preserve provider-neutral adoption.

---

## 6) Entitlement and Packaging Strategy

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

## 7) Revenue Metrics and Leading Indicators

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

## 8) Pricing Motion (Non-Numeric Framework)

Recommend blended model:
- platform subscription by tier,
- usage dimensions tied to tenant scale and governance workload,
- add-on packages for enterprise governance/compliance features,
- early design-partner or assisted-production engagements while platform maturity is still being proven.

Avoid billing model that incentivizes bypassing deterministic safety path or over-rewarding raw tool volume before operational maturity is proven.

---

## 9) Sales Narrative Anchors

Primary narrative:
- "Keep your models and providers; use one governance and reliability model."

Secondary anchors:
- "Stop unsafe AI actions from becoming unsafe system actions."
- "Switch providers without rewriting governance."
- "Enforce policy before side effects."
- "Produce audit evidence by API, not manual operations."
- "Scale tenants with fairness and controls, not best-effort chaos."

---

## 10) Current Go-to-Market Posture

Recommended near-term posture:

1. Start with design-partner or assisted-production pilots, not broad self-serve enterprise claims.
2. Target workflows where agents can trigger real system side effects.
3. Prove value with blocked unsafe actions, deterministic coverage, audit evidence, and reduced debugging/incident effort.
4. Productize deployment, telemetry, and auth hardening before expanding commercial claims aggressively.

This keeps messaging aligned with current platform maturity while building evidence for stronger monetization later.

### 10a) Technical self-serve vs commercial enterprise posture (no contradiction)

Two ideas must stay **explicitly separated** in sales, docs, and agent-generated copy:

| Axis | Meaning |
|------|---------|
| **Technical self-serve** | Customers configure tenants, policies, ingress, tools, providers, and audit consumption **via public APIs** without requiring a vendor engineer in the loop for each change. This is the **default integration and product mechanics** — see [`customer-self-serve-governance-journey.md`](customer-self-serve-governance-journey.md) and [`foundation-tier-adoption-checklist.md`](foundation-tier-adoption-checklist.md). |
| **Commercial / enterprise claims** | Marketing and contract language avoid **unsupported** assertions (“full enterprise self-serve,” “compliance-complete everywhere”) until deployment, telemetry, auth, and evidence bundles meet the maturity called out in §14 prerequisites and `governed-execution-positioning.md`. **Design-partner and assisted pilots** remain valid GTM while evidence deepens. |

**Rule for agents:** Never use §10 to argue against shipping **API-first tenant governance**; use §10 to gate **external promises** and **support SLAs**, not the existence of customer-controlled configuration APIs.

---

## 11) Monetization Risks and Mitigations

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

6. **Risk: Product feels like an optional dashboard instead of a mandatory control boundary**
   - Mitigation: sell governed execution for risky actions, not observability alone.

7. **Risk: Split-brain config between customer adapters and eXo-brain**
   - Mitigation: keep provider-native settings customer-owned and governance settings eXo-brain-owned.

---

## 12) Alignment with Core and Adapter Strategy

Monetization must not violate architecture:
- no premium shortcut that bypasses policy/deterministic guards,
- no adapter-specific private bypass inside core,
- no paid feature that weakens tenant isolation or audit guarantees.
- no monetization model that requires all customers to route raw data through a shared hosted deployment when dedicated/private deployment is the trust requirement.

Premium value should reinforce, not compromise, platform invariants.

---

## 13) Execution Plan (Business + Engineering)

1. Publish the governed-execution product boundary and ICP guidance alongside tier docs.
2. Define entitlement matrix for Foundation/Pro/Enterprise.
3. Define governance ingress product model (profiles, custom rules, optional plugin packs, performance SLOs).
4. Bind entitlement checks to explicit API/config control points.
5. Add entitlement + gate-decision observability in audit and runtime admin endpoints.
6. Publish feature boundary documentation and onboarding playbooks.
7. Review quarterly against adoption, governance usage, and retention metrics.

---

## 14) Decision Checklist

- Does this strengthen eXo-brain as a mandatory governed execution boundary rather than an optional add-on?
- Does this monetization decision preserve core trust guarantees?
- Does it keep provider neutrality intact?
- Does it keep provider/model connectivity customer-owned where possible?
- Is entitlement enforcement explicit and testable?
- Does the pricing boundary align with actual customer value?
- Does this improve long-term retention rather than short-term lock-in?

If any answer is "no", revise before rollout.
