<!--
File: backlog-reconciliation-v2-execution-board.md
Path: docs/plans/backlog-reconciliation-v2-execution-board.md
Role: Approval-ready P0/P1/P2 execution board after P2 expansion closure.
Used By:
 - Maintainer implementation planning workflow
 - Future slice execution and PR packaging
Depends On:
 - docs/plans/tenant-tool-execution-architecture.md
 - docs/plans/p2-expansion-roadmap.md
 - .cursor/research-for-refactor/06-mvp-build-sequence.md
 - .cursor/research-for-refactor/12-bootstrap-checklist.md
Notes:
 - This board is planning-only until explicitly approved for coding.
-->

# Backlog Reconciliation V2 Execution Board

Date: 2026-03-05  
Actor: Savin I. Razvan  
Agent/s: gpt-5.3-codex

## Scope

Define the next approved execution queue after closure of:
- P2 expansion baseline
- P2-1 autoscaling/backpressure
- P2-2 DLQ/replay
- P2-3 conflict resolution
- P2-4 tenancy/cost governance instrumentation

## Current State Summary

- `docs/plans/p2-expansion-roadmap.md` is closed (no open P2 items).
- `.local/alignment-audit.md` and `.local/alignment-todos.md` are closed snapshots for the completed P2 track.
- P0 docs/data-safety sequence is completed (`p0-1`, `p0-2`, `p0-3`).
- P1-1 governance metrics export contract is completed.
- P1-2 tenant budget window policy is completed.
- P1-3 governance alert evidence bundle is completed.
- P2-1 BYOC recovery chaos suite is completed.
- P2-2 governance anomaly detectors are completed.

## Proposed Execution Order (Approval Required)

### P0 (must land first)

1. `p0-1-doc-state-reconciliation`
   - Objective: remove stale "open P2 queue" wording and make docs status fully consistent.
   - Scope:
     - `docs/plans/tenant-tool-execution-architecture.md`
     - `.local/alignment-audit.md`
     - `.local/alignment-todos.md`
   - Acceptance:
     - plan and `.local` artifacts all state P2 queue is closed
     - only one canonical "next queue source" pointer remains
   - Rollback/Fallback:
     - revert doc-only commit if any contradiction is introduced

2. `p0-2-local-data-durability-baseline`
   - Objective: prevent local runtime-data loss during cleanup/reset operations.
   - Scope:
     - add restore-safe backup/export script for `.exo_data/exo.db`
     - add runbook procedure for backup/restore and validation
   - Acceptance:
     - backup script produces deterministic artifact
     - restore script recreates functional DB in clean workspace
     - validation script confirms required schema/tables
   - Rollback/Fallback:
     - keep existing runtime startup path unchanged; disable new scripts if they fail

3. `p0-3-rc-signoff-data-safety-gate`
   - Objective: include local data safety checks in RC signoff evidence.
   - Scope:
     - extend signoff checklist/gates with backup integrity + restore drill result
   - Acceptance:
     - `make rc-signoff` captures data-safety evidence section
     - parser output includes data-safety gate status
   - Rollback/Fallback:
     - preserve existing rc-signoff pass behavior behind non-blocking flag until validated

### P1 (operational productization)

1. `p1-1-governance-metrics-export-contract`
   - Objective: expose structured tenant governance metrics for dashboards/alerts.
   - Scope:
     - add API contract for tenant governance metrics export
     - include rejection reason rollups and cost utilization windows
   - Acceptance:
     - API tests cover shape, tenant scoping, and deterministic counters
   - Rollback/Fallback:
     - keep existing runtime-control fields; add export path as additive only

2. `p1-2-tenant-budget-window-policy`
   - Objective: add time-window budget semantics (period reset + limits) for BYOC cost governance.
   - Scope:
     - policy/config wiring for windowed budgets
     - deterministic reset behavior and reason codes
   - Acceptance:
     - tests for reset boundaries, over-budget rejection, and recovery next window
   - Rollback/Fallback:
     - fallback to current lifetime-counter model when window policy disabled

3. `p1-3-governance-alert-evidence-bundle`
   - Objective: include governance alert signals in release evidence workflow.
   - Scope:
     - alert thresholds + evidence extraction in ops docs/checklist
   - Acceptance:
     - evidence artifact includes governance alert section with normalized fields
   - Rollback/Fallback:
     - keep governance alert section advisory-only if data unavailable

### P2 (scale and hardening extensions)

1. `p2-1-byoc-recovery-chaos-suite`
   - Objective: add high-stress failure/recovery tests for sqlite-backed BYOC stores.
   - Scope:
     - lease expiry storms, restart races, replay collisions, conflict strategy under load
   - Acceptance:
     - deterministic pass across repeated runs in CI
   - Rollback/Fallback:
     - quarantine flaky scenarios under explicit marker until stabilized

2. `p2-2-governance-anomaly-detectors`
   - Objective: detect abnormal tenant-level cost/rejection patterns for triage.
   - Scope:
     - detector policy module + reason-code anomaly thresholds
   - Acceptance:
     - deterministic detector outputs and unit tests for known patterns
   - Rollback/Fallback:
     - non-blocking alert mode only (no runtime admission impact)

3. `p2-3-byoc-multi-tenant-budget-fairness`
   - Objective: improve fairness under concurrent tenant contention.
   - Scope:
     - admission weighting/fairness policy with deterministic tie-break behavior
   - Acceptance:
     - fairness simulations show no tenant starvation under configured limits
   - Rollback/Fallback:
     - revert to existing first-come behavior when fairness policy disabled

## Global Acceptance Gates (for every slice)

- `python -m pytest -q`
- `python scripts/architecture/validate_layers.py`
- `python scripts/architecture/scan_forbidden_imports.py`
- companion tracker synchronization:
  - `.cursor/research-for-refactor/06-mvp-build-sequence.md`
  - `.cursor/research-for-refactor/12-bootstrap-checklist.md`

## Immediate Next Step

Next implementation target: `p2-3-byoc-multi-tenant-budget-fairness`.
