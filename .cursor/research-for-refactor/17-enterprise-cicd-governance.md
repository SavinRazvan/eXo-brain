# Enterprise CI/CD Governance

## Goal
Define a production-grade CI/CD governance model for the framework so delivery is secure, repeatable, and policy-enforced across adapters, agents, tools, MCP integrations, and enterprise modules.

## Scope
This document operationalizes release flow using:
- `15-enterprise-quality-gates.md` (go/no-go thresholds)
- `16-enterprise-testing-strategy.md` (test architecture and gate execution)

## Current Repository Implementation Status
- CI architecture fitness workflow: implemented in `.github/workflows/architecture-fitness.yml`.
- Automated full test execution (`python -m pytest -q`): implemented in CI.
- Release candidate workflow: implemented in `.github/workflows/release-candidate.yml`.
- Progressive deploy workflow with rollback hook: implemented in `.github/workflows/progressive-deploy.yml`.
- Release governance scripts:
  - `scripts/release/verify_gates.py`
  - `scripts/release/verify_provenance.py`
  - `scripts/release/rollback_release.py`
- Release config baselines:
  - `configs/release/gate_thresholds.yaml`
  - `configs/release/rollout_policies.yaml`

## Delivery Principles
- Every deployment is traceable to signed source + signed artifacts.
- Promotion across environments is evidence-based, not manual guesswork.
- `P0` gate failures block deployment automatically.
- Rollout must support progressive exposure and one-step rollback.
- Configuration and policy changes follow the same governance as code.

## Environment Topology
- `dev`: rapid integration and early validation.
- `stage`: production-like validation and final gate enforcement.
- `prod`: progressive rollout only (canary -> partial -> full).

Each environment has:
- isolated secrets and credentials
- tenant-aware policy overlays
- dedicated observability and audit sinks

## Pipeline Architecture

## 1) Source and Commit Controls
Required:
- branch protection on main release branches
- required reviews for architecture/security-sensitive paths
- signed commits or provenance-attested merges
- mandatory change ticket/trace ID in PR metadata

Fail action:
- reject merge until controls pass.

## 2) Build and Supply Chain Stage
Required:
- deterministic build process (lockfiles/pinned dependency strategy)
- SBOM generation for every artifact
- dependency vulnerability and license scanning
- artifact signing and provenance attestation

Fail action:
- block artifact publish.

## 3) Verification Stage (Pre-Promotion)
Required:
- run test tracks defined in `16-enterprise-testing-strategy.md`
- run quality thresholds from `15-enterprise-quality-gates.md`
- policy regression tests for high-risk operations
- adapter compatibility matrix checks
- architecture fitness CI checklist from `35-architecture-fitness-ci-checklist.md`

Fail action:
- block promotion to next environment.

## 4) Release Candidate Stage
Required:
- immutable release candidate tag
- evidence bundle attached (tests, SLO snapshot, audit checks, security scan)
- release notes generated with risk/classification summary

Fail action:
- do not mark candidate as deployable.

## 5) Progressive Deployment Stage
Required:
- canary rollout with explicit blast-radius limits
- automated health checks (error rate, latency, cost, queue depth)
- rollback triggers and auto/assisted rollback path

Fail action:
- immediate rollback to last known good.

## 6) Post-Deploy Governance
Required:
- post-deploy verification jobs complete
- SLO burn-rate check remains under threshold
- audit event confirms release activation and final state
- deployment record linked to evidence bundle and incident timeline (if any)

Fail action:
- freeze further promotions and open incident.

## Gate Policy Enforcement

Gate categories:
- `SecurityGate`
- `QualityGate`
- `ComplianceGate`
- `ReliabilityGate`
- `GovernanceGate`

Rules:
- any `P0` failure -> hard stop
- repeated `P1` degradation -> promotion freeze pending review
- `P2` failures -> track with remediation deadline

## Rollback and Recovery Policy
- always keep one-step rollback artifact + config snapshot
- rollback must restore:
  - runtime binaries/artifacts
  - policy bundles
  - model/provider routing config
  - feature-flag state
- recovery test must be executed at least once per release train

## Release Trains and Cadence
- standard train: weekly or bi-weekly depending on risk profile
- emergency train: expedited but still must pass minimum `P0` gates
- large architectural changes: gated behind staged flag rollout

## Governance for Non-Code Changes
Treat as deployable artifacts:
- policy rules
- model/provider registry entries
- workflow templates
- tenant override configs

All require:
- schema validation
- approval workflow
- audit trail linkage

## Required Metrics Dashboard
Minimum dashboards per environment:
- deployment frequency
- lead time for changes
- change failure rate
- MTTR
- canary success/failure trend
- gate pass/fail trend by category
- budget variance by release

## Compliance and Audit Requirements
- immutable release ledger with:
  - artifact digest
  - source revision
  - approvers
  - gate results
  - rollout timeline
- exportable evidence pack for internal/external audits
- retention policy aligned to compliance profile

## Suggested File Hooks In New Repo
- `.github/workflows/architecture-fitness.yml`
- `.github/workflows/release-candidate.yml`
- `.github/workflows/progressive-deploy.yml`
- `scripts/release/verify_gates.py`
- `scripts/release/verify_provenance.py`
- `scripts/release/rollback_release.py`
- `configs/release/gate_thresholds.yaml`
- `configs/release/rollout_policies.yaml`
- `docs/releases/RELEASE_TEMPLATE.md`

## 30-Day CI/CD Hardening Plan

Week 1:
- baseline CI with unit/contract/security/dependency gates
- branch protections and review rules

Week 2:
- release-candidate pipeline with evidence bundle generation
- artifact signing + SBOM + provenance checks

Week 3:
- progressive rollout automation with canary checks and rollback
- post-deploy SLO and audit verification jobs

Week 4:
- governance dashboards + failure policy tuning
- first full dry-run of incident + rollback drill

## Exit Criteria (Enterprise CI/CD Ready)
- all deployments flow through gated CI/CD only (no ad-hoc manual deploy path)
- provenance and signing are enforced for all production artifacts
- progressive rollout and rollback automation validated
- release evidence bundles are complete and auditable
- change governance applies equally to code, policy, and model/provider config

## Related Docs
- `12-bootstrap-checklist.md`
- `14-enterprise-readiness-modules.md`
- `15-enterprise-quality-gates.md`
- `16-enterprise-testing-strategy.md`
- `18-enterprise-operational-runbooks.md`
- `35-architecture-fitness-ci-checklist.md`
