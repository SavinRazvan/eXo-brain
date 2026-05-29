<!--
File: module-hardening-slice-checklist.md
Path: docs/roadmap/module-hardening-slice-checklist.md
Role: Per-PR checklist for module hardening slices.
Used By:
 - docs/roadmap/enterprise-module-hardening-integration-plan.md
Depends On:
 - docs/roadmap/enterprise-module-hardening-integration-plan.md
 - docs/modules/README.md
 - scripts/pr/prepare.py
Notes:
 - Last reviewed: 2026-05-29
-->

# Module Hardening Slice Checklist

Use this checklist in each module-hardening PR to keep execution consistent and auditable. Preserve **control plane** enforcement (no policy bypass); **provider runtime adapters** stay southbound only per [workspace-architecture.md](../architecture/workspace-architecture.md). Update the matching [docs/modules/*.md](../modules/README.md) when contracts change.

## Slice Header
- Slice name:
- Module group:
- Branch:
- Rollback strategy:
- Fallback behavior:

## A) Contract + Validation
- [ ] Inputs validated at module boundary
- [ ] Output/error envelope contract confirmed
- [ ] Policy pre-checks and post-checks applied where needed

## B) Logging + Observability
- [ ] Correlation IDs propagated (`job/task/agent/tool`)
- [ ] Structured logs for key decisions (allow/deny/escalate/retry/fallback)
- [ ] Tenant/identity context included where applicable
- [ ] Secret redaction expectations preserved

## C) Error Handling
- [ ] Typed errors for expected failure classes
- [ ] Deterministic fallback/blocked envelope for controlled failures
- [ ] No silent catch-and-ignore paths
- [ ] Retryability is explicit for transient failures

## D) Testing
- [ ] Unit tests: happy path
- [ ] Unit tests: failure path
- [ ] Unit tests: edge/malformed input path
- [ ] Integration tests updated for touched module boundaries
- [ ] Replay/retry tests added when behavior is stateful or high-impact

## E) Gates
- [ ] `python scripts/pr/prepare.py` gates green (or equivalent: `check_testing_artifacts.py`, `pytest -q`, `validate_layers.py`, `scan_forbidden_imports.py`)
- [ ] `python scripts/architecture/check_governance_consistency.py` when governance/workflows/policy docs touched
- [ ] Relevant module subset tests pass (`tests/modules/<area>/`)
- [ ] Architecture-impacting: `alignment-audit.md` / `alignment-todos.md` refreshed ([alignment-audit-schema.md](alignment-audit-schema.md))

## F) Evidence + Docs
- [ ] `.local/workflow-artifacts/pr/review.md` updated with findings and recommendation
- [ ] `.local/workflow-artifacts/pr/prep.md` updated with gate evidence
- [ ] `.local/workflow-artifacts/pr/merge.md` updated in merge phase with merge evidence and follow-ups
- [ ] `docs/modules/*` and/or `docs/api/customer-api-integration-guide.md` updated for changed contracts
- [ ] CI workflow paths verified if tests/scripts moved (`.github/workflows/`)

## G) Release Readiness Decision
- [ ] READY for merge
- [ ] NEEDS WORK (list blockers)
- [ ] NEEDS DISCUSSION (list open decisions)
