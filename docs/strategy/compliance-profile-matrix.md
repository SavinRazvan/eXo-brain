<!--
File: COMPLIANCE_PROFILE_MATRIX.md
Path: compliance-profile-matrix.md
Role: Industry and compliance profile mapping from control objectives to eXo-brain product surfaces and evidence artifacts.
Used By:
 - goal.md
 - monetization-strategy.md
 - deployment-models.md
 - traceability-matrix.md
Depends On:
 - src/policies/*
 - src/audit/*
 - src/api/routers/audit.py
 - src/api/routers/runtime_control.py
 - scripts/release/verify_gates.py
Notes:
 - This is a product-readiness map, not legal certification advice.
-->

# Compliance Profile Matrix

## Governance Metadata

- Status: `active`
- Owner: `Savin I. Razvan`
- Version: `1.0.1`
- Last Reviewed: `2026-03-24`
- Review Cadence: `monthly`
- Decision Scope: `Phased compliance-readiness profiles and enterprise control mapping for go-to-market sequencing.`

## 1) Scope and Boundaries

- This matrix defines compliance-readiness expectations for product strategy.
- This matrix is not legal advice and is not a substitute for formal certification or legal review.
- Product narrative for the **control plane** safety boundary and customer integration surfaces is aligned with [`docs/plans/control-plane-product-alignment-plan.md`](../plans/control-plane-product-alignment-plan.md); compliance **claims** must still map row-by-row to controls and evidence below.
- Terminology used:
  - `Readiness`: product controls and evidence are designed and operationally testable.
  - `Certification`: an external audit/attestation process completed by qualified assessors.

---

## 2) Wave Model (Locked)

- `Wave 1 (launch baseline)`: SOC2 + GDPR readiness for AI-native B2B SaaS.
- `Wave 2`: HIPAA-ready profile expansion.
- `Wave 3`: PCI/public-sector-ready profile expansion.

This sequencing prioritizes practical enterprise adoption without overextending early-stage operations.

---

## 3) Profile-to-Control Matrix

| Wave | Compliance profile | Target industries / buyers | Core control objectives | eXo-brain product surfaces | Evidence artifacts | Current status | Owner | Known gaps / blockers |
|---|---|---|---|---|---|---|---|---|
| Wave 1 | SOC2-ready | B2B SaaS, platform teams, internal enterprise innovation groups | Access control, change management, auditability, incident response, operational reliability | `src/api/middleware/auth.py`, `src/access_control/*`, `src/audit/*`, `src/api/routers/runtime_control.py`, architecture/release scripts | RC signoff artifacts, audit report/export/verify responses, runtime control stats snapshots | Baseline in progress | Savin I. Razvan | Formal control narratives and auditor evidence packaging need expansion |
| Wave 1 | GDPR-ready | EU-facing SaaS/platform tenants | Data governance, purpose limitation support, auditability of processing actions, retention/cleanup controls | audit cleanup/export endpoints, retention controls in runtime/audit flows, policy overlays | audit event list/report/export bundles, cleanup endpoint evidence, governance docs | Baseline in progress | Savin I. Razvan | DSAR-specific operational runbooks and data classification map need explicit documentation |
| Wave 2 | HIPAA-ready | Healthcare SaaS, health data workflows, covered-entity-adjacent platforms | Access controls, activity logs, integrity controls, operational safeguards, tenant isolation | auth + RBAC layers, audit chain integrity, tenant isolation controls, deterministic tool governance | audit chain verification outputs, auth/rbac test evidence, tenant isolation test evidence | Planned | Savin I. Razvan | BAAs, PHI handling boundaries, and healthcare-specific incident workflows not yet codified |
| Wave 3 | PCI-ready (scope-limited) | Fintech adjacent workflows where payment data boundaries matter | Strong segmentation, access minimization, logging, strict change controls, controlled operational runtime | deployment segmentation model, authz, audit, strict runtime controls | release evidence, audit/export verification, deployment boundary documentation | Planned | Savin I. Razvan | Formal cardholder data environment boundary model and assessor-ready controls not yet defined |
| Wave 3 | Public-sector-ready (pre-FedRAMP posture) | Gov-adjacent enterprise teams needing higher assurance operations | Strong operational governance, traceability, strict configuration/change control, hardened deployment model | dedicated deployment model, runtime governance controls, audit export/verify workflows, release gates | signed evidence bundles, RC signoff outputs, deployment responsibility documentation | Planned | Savin I. Razvan | Control inheritance model and public-sector compliance packaging not yet defined |

---

## 4) Control Family Mapping (Cross-Profile)

| Control family | Primary product anchors | Test anchors | Evidence anchors |
|---|---|---|---|
| Identity and access | `src/api/middleware/auth.py`, `src/access_control/*` | `tests/modules/api/test_auth_jwt.py`, `tests/modules/api/test_auth_apikey.py`, `tests/modules/access_control/test_access_control_*` | auth API behavior logs, RC signoff + test outputs |
| Policy-governed execution | `src/policies/middleware.py`, `src/tools/executor.py` | `tests/modules/policies/test_policy_risk_gates.py`, `tests/modules/policies/test_deterministic_tool_replay.py` | runtime event traces, policy decision outcomes |
| Audit and evidence integrity | `src/audit/*`, `src/api/routers/audit.py` | `tests/modules/audit/test_audit_chain_integrity.py`, `tests/modules/audit/test_evidence_bundle_generation.py`, `tests/modules/api/test_audit_api.py` | `/admin/audit/export`, `/admin/audit/export-file`, `/admin/audit/verify` outputs |
| Tenant isolation and governance | `src/runtime/tenant_runtime.py`, `src/tenancy/*` | `tests/modules/runtime/test_tenant_runtime.py`, `tests/modules/persistence/test_cross_tenant_isolation.py` | tenant-scoped runtime/audit endpoint evidence |
| Operational reliability controls | `src/core/*`, `src/resilience/*`, `src/api/routers/runtime_control.py` | `tests/modules/core/test_background_runtime_cancel_resume.py`, `tests/modules/resilience/test_retry_idempotency_guards.py` | runtime control stats, cancellation evidence, RC signoff gates |

---

## 5) Industry Packaging Recommendations

- Default launch profile:
  - Position `SOC2 + GDPR readiness` only as control-mapping direction for
    SaaS and AI platform teams; do not present it as certification or current
    vendor-readiness.
- Expansion profile:
  - Introduce healthcare and fintech/public-sector readiness only after entitlement and deployment boundaries are fully enforceable.
- Sales discipline:
  - Use readiness claims only when they are tied to documented controls and
    artifacts.
  - Do not sell certification claims before formal external attestation.

---

## 6) Readiness Gaps and Sequencing

Priority backlog:

1. Formal entitlement enforcement layer (ties premium controls to contractual tiers).
2. Compliance evidence catalog with control-to-artifact references.
3. DSAR/privacy operations playbook references (GDPR operational clarity).
4. Deployment responsibility model alignment (needed for HIPAA/PCI/public-sector readiness claims).
5. External audit preparation checklist for SOC2 evidence packaging.

---

## 7) Change Control Checklist

- Does the change alter a compliance-readiness claim?
- Is the affected profile row updated with owner and status?
- Are test/evidence anchors still valid?
- Is wording clear on readiness vs certification?

If any answer is "no", update this matrix before merge.
