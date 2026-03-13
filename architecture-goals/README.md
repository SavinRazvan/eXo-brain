<!--
File: README.md
Path: architecture-goals/README.md
Role: Index and reading order for strategic architecture goals and execution guardrails.
Used By:
 - architecture-goals/GOAL.md
 - architecture-goals/CORE.md
 - architecture-goals/ADAPTER_STRATEGY.md
 - architecture-goals/MONETIZATION_STRATEGY.md
 - architecture-goals/ENTITLEMENT_MATRIX.md
 - architecture-goals/COMPLIANCE_PROFILE_MATRIX.md
 - architecture-goals/DEPLOYMENT_MODELS.md
 - architecture-goals/INTERFACE_STRATEGY.md
 - architecture-goals/TRACEABILITY_MATRIX.md
Depends On:
 - AGENTS.md
 - docs/plans/tenant-tool-execution-architecture.md
Notes:
 - Keep this index synchronized when adding or retiring architecture-goals documents.
-->

# Architecture Goals Index

## Governance Metadata

- Status: `active`
- Owner: `Savin I. Razvan`
- Version: `1.0.0`
- Last Reviewed: `2026-03-12`
- Review Cadence: `monthly`
- Decision Scope: `Folder-level indexing, reading order, and strategy document governance for architecture-goals.`

## Purpose

This folder contains strategic documents that define product direction, non-negotiable boundaries, monetization posture, and operational traceability.

These documents are intended to prevent direction drift while implementation evolves.

## Reading Order

1. `architecture-goals/GOAL.md`  
   Product north-star, problems solved, and platform boundary.
2. `architecture-goals/CORE.md`  
   Core invariants, governance enforcement, and safety-critical architecture decisions.
3. `architecture-goals/ADAPTER_STRATEGY.md`  
   Adapter ecosystem strategy, packaging, certification, and fallback behavior.
4. `architecture-goals/MONETIZATION_STRATEGY.md`  
   Monetization model, tier boundaries, and value capture strategy.
5. `architecture-goals/ENTITLEMENT_MATRIX.md`  
   Feature-to-tier enforcement and evidence matrix for monetization operability.
6. `architecture-goals/COMPLIANCE_PROFILE_MATRIX.md`  
   Phased compliance-readiness profiles and control/evidence mapping.
7. `architecture-goals/DEPLOYMENT_MODELS.md`  
   Deployment packaging and support boundaries by model and tier.
8. `architecture-goals/INTERFACE_STRATEGY.md`  
   API-first experience strategy and UI roadmap constraints.
9. `architecture-goals/TRACEABILITY_MATRIX.md`  
   Decision-to-code and decision-to-test mapping for drift detection.

## Update Policy

- Update strategic docs before or alongside architecture-impacting implementation slices.
- Keep boundaries aligned with `AGENTS.md` and canonical operational plans.
- Use `TRACEABILITY_MATRIX.md` to verify each strategic decision still maps to concrete code/tests/APIs.

## Change Control Rule

- Any architecture-impacting strategy change must update:
  - the affected strategy doc(s),
  - `architecture-goals/TRACEABILITY_MATRIX.md`,
  - this index when document set or reading order changes.
- If there is uncertainty, mark the section as `Draft Decision` with owner and review date instead of leaving ambiguity.

## Scope Boundaries

- These documents define strategy and constraints.
- Detailed implementation contracts remain in module docs under `docs/modules/`.
- Operational runbooks remain under `docs/operations/`.

## Closure Snapshot (2026-03-12)

Now enforceable in strategy package:
- governance metadata standardization across all architecture-goals docs,
- entitlement matrix with enforceable vs planned capability flags,
- compliance profile matrix with phased wave model,
- deployment model strategy with support and tier posture,
- cross-document traceability anchors.

Still planned (not yet fully implemented in product controls):
- hard entitlement middleware with tier-aware API/policy gating,
- deployment certification path for private/self-hosted support,
- expanded compliance artifact catalog and profile-specific runbooks.

Next implementation slice entrypoints:
- entitlement enforcement layer (API/config/policy gate integration),
- tier-aware audit evidence for entitlement decisions,
- deployment certification and support-boundary automation.
