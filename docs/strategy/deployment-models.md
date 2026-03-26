<!--
File: DEPLOYMENT_MODELS.md
Path: deployment-models.md
Role: Canonical deployment model strategy for enterprise packaging, support boundaries, and SLA posture.
Used By:
 - goal.md
 - monetization-strategy.md
 - compliance-profile-matrix.md
 - traceability-matrix.md
Depends On:
 - src/api/*
 - src/runtime/*
 - src/tenancy/*
 - src/policies/*
 - src/audit/*
 - scripts/release/*
Notes:
 - Canonical launch posture is SaaS-first with dedicated VPC expansion.
 - Private/self-hosted remains a deferred option until operational maturity gates are met.
-->

# Deployment Models

## Governance Metadata

- Status: `active`
- Owner: `Savin I. Razvan`
- Version: `1.2.0`
- Last Reviewed: `2026-03-24`
- Review Cadence: `monthly`
- Decision Scope: `Deployment model definitions, responsibilities, support posture, and tier alignment.`

## 1) Purpose

Define explicit deployment models and support boundaries so enterprise GTM, pricing, and operations are aligned with platform reality.

This document answers:
- where workloads run,
- who owns what responsibilities,
- what SLA posture is realistic by model,
- how models map to tier packaging and compliance readiness,
- how observability export and provider-connectivity ownership should be handled by model,
- how **customer bridge** integrations (HTTP, optional `/v1`, future SDK) still terminate on the **hosted control plane** for enforcement (see `governed-execution-positioning.md` and [`docs/plans/control-plane-product-alignment-plan.md`](../plans/control-plane-product-alignment-plan.md)).

---

## 2) Locked Deployment Sequencing

- Launch default: **Shared multi-tenant SaaS**.
- Enterprise expansion: **Dedicated single-tenant/VPC**.
- Deferred option: **Private/self-hosted** when operations and support maturity are sufficient.

Reasoning:
- maximizes early delivery speed while preserving enterprise upgrade path.

---

## 3) Model Definitions

## Model A - Shared Multi-Tenant SaaS

### Responsibility split

- Platform owner:
  - control plane and data plane operations,
  - runtime governance and audit systems,
  - upgrade lifecycle and incident response.
- Customer:
  - provider credentials and provider-native adapter/account configuration,
  - tenant-level configuration (providers, policies, agents, quotas),
  - business data and workflow design.

### Data/control plane boundary

- Control plane and execution services are managed by platform.
- Tenant isolation enforced logically (tenant-scoped registries/policies/sessions/audit paths).
- Customer-owned provider connectivity may be configured through adapters or deployment-local settings without changing the platform governance boundary.

### Observability posture

- Runtime/audit APIs remain authoritative for governance evidence.
- Standard telemetry export (OpenTelemetry/Prometheus) should be offered as a supported sink when the shared SaaS profile is productized for enterprise operations.

### Support and SLA posture

- Foundation and Pro baseline support.
- SLA target can be tiered, but shared tenancy imposes stricter noisy-neighbor and fairness controls.

### Security/compliance fit

- Best fit for SOC2-ready and GDPR-ready launch profiles.
- Requires strong tenant isolation evidence and runtime governance controls.

### Upgrade and incident model

- Managed rolling upgrades with maintenance policy windows.
- Centralized incident response with tenant-scoped impact analysis.

---

## Model B - Dedicated Single-Tenant / VPC

### Responsibility split

- Platform owner:
  - managed deployment in dedicated account/VPC profile,
  - release management, security patches, control-plane reliability.
- Customer:
  - provider credentials and provider-native adapter/account configuration,
  - network/access constraints and optional shared-responsibility inputs,
  - workflow and data governance policy definitions.

### Data/control plane boundary

- Tenant receives isolated deployment boundary.
- Stronger network and runtime isolation posture than shared SaaS.

### Observability posture

- Runtime/audit APIs remain authoritative for governance evidence.
- OpenTelemetry/Prometheus export should integrate with customer-approved sinks and incident tooling.

### Support and SLA posture

- Enterprise primary model.
- Higher support expectations and stronger contractual SLA posture.

### Security/compliance fit

- Better fit for regulated-lite and enterprise procurement needs.
- Preferred stepping stone for HIPAA-ready and higher-assurance profiles.

### Upgrade and incident model

- Coordinated release windows per tenant.
- Tenant-specific incident handling, rollback, and evidence packaging.

---

## Model C - Private / Self-Hosted (Deferred, Optional)

### Responsibility split

- Platform owner:
  - distribution artifacts, compatibility guidance, documented support boundaries.
- Customer:
  - provider credentials and provider-native adapter/account configuration,
  - infrastructure operations, security hardening, reliability operations, incident response execution.

### Data/control plane boundary

- Customer owns deployment and operations boundary.
- Platform provides product and support interfaces as contracted.

### Observability posture

- Customer operates telemetry sinks in their environment.
- Supported self-hosted profiles should document exporter configuration, redaction guarantees, and health/failure behavior for OpenTelemetry/Prometheus integrations.

### Support and SLA posture

- Deferred from initial launch.
- Support is constrained by certified deployment profiles and version matrix.

### Security/compliance fit

- Can support strict enterprise requirements where customer requires operational control.
- Requires explicit control inheritance and operational responsibility documentation.

### Upgrade and incident model

- Customer-managed upgrades with platform-certified version windows.
- Joint incident model with defined escalation and evidence interfaces.

---

## 4) Tier Alignment (Policy-Level)

| Deployment model | Foundation | Pro | Enterprise | Notes |
|---|---|---|---|---|
| Shared multi-tenant SaaS | Primary | Primary | Supported | Default launch model |
| Dedicated single-tenant/VPC | Not default | Optional by agreement | Primary | Enterprise expansion path |
| Private/self-hosted | Planned (not default) | Planned (not default) | Optional after maturity gates | Deferred until support model is hardened |

Policy note:
- Tier packaging is governance-depth first; deployment model availability is an additional enterprise packaging dimension.

---

## 5) SLA Posture Guidance (Non-Contractual Strategy)

- Foundation:
  - best-effort baseline with transparent operational metrics.
- Pro:
  - tiered operational commitments with stronger governance visibility.
- Enterprise:
  - strongest support/SLA posture, especially for dedicated deployments.

Do not publish contractual SLA claims before entitlement gating and deployment operations are fully enforceable.

---

## 6) Compliance Fit by Deployment Model

| Compliance readiness profile | Shared SaaS | Dedicated VPC | Private/self-hosted |
|---|---|---|---|
| SOC2-ready | Strong fit | Strong fit | Possible with customer controls |
| GDPR-ready | Strong fit | Strong fit | Possible with customer controls |
| HIPAA-ready | Conditional | Better fit | Conditional with strict shared-responsibility model |
| PCI/public-sector-ready | Conditional | Better fit | Potential fit after maturity and control inheritance definition |

---

## 7) Operational Maturity Gates for Private/Self-Hosted

Private/self-hosted should remain `Planned` until:

1. entitlement controls are explicitly enforced and auditable,
2. deployment certification matrix is documented,
3. upgrade compatibility policy is automated and tested,
4. incident and evidence exchange runbooks are productized,
5. support boundaries are contract-ready and repeatable,
6. supported observability export profiles (including OpenTelemetry/Prometheus expectations) are documented and validated.

---

## 8) Open Decisions

1. Minimum supported versions policy for self-hosted customers.
2. Customer-managed observability requirements and minimum OpenTelemetry/Prometheus support expectations for supported incident response.
3. Whether private adapter certification is mandatory for enterprise self-hosted production.
4. Exact SLA commitments by tier and deployment model.

---

## 9) Change Control Checklist

- Does this change alter deployment responsibilities or support boundaries?
- Is tier mapping still aligned with monetization and entitlement strategy?
- Are compliance-fit statements still accurate for each model?
- Are deferred models still clearly marked as `Planned`?

If any answer is "no", update this document before merge.
