<!--
File: backlog-reconciliation-v3-execution-board.md
Path: docs/archive/plans/backlog-reconciliation-v3-execution-board.md
Role: Approval-ready execution board for post-v2 implementation planning.
Used By:
 - Maintainer implementation planning workflow
 - Future slice execution and PR packaging
Depends On:
 - docs/plans/tenant-tool-execution-architecture.md
 - docs/archive/plans/backlog-reconciliation-v2-execution-board.md
 - .local/index-and-planning/current/plan.md
 - .local/index-and-planning/current/work-tracker.md
Notes:
 - This board is planning-only until explicitly approved for coding.
-->

# Backlog Reconciliation V3 Execution Board

> Status: Archived historical plan.
> Canonical replacement: `docs/plans/tenant-tool-execution-architecture.md`
> Archived on: 2026-03-19
> Archive reason: superseded

Date: 2026-03-05  
Actor: Savin I. Razvan  
Agent/s: gpt-5.3-codex

## Scope

Define the next approved queue after closure of backlog reconciliation v2:
- `p1-2-tenant-budget-window-policy`
- `p1-3-governance-alert-evidence-bundle`
- `p2-1-byoc-recovery-chaos-suite`
- `p2-2-governance-anomaly-detectors`
- `p2-3-byoc-multi-tenant-budget-fairness`

## Current State Summary

- `docs/archive/plans/backlog-reconciliation-v2-execution-board.md` is closed (no open queue items).
- BYOC governance control plane now includes:
  - cost windows
  - advisory governance alerts
  - anomaly detectors
  - fair-admission policy gating
- Runtime and architecture fitness gates are passing in current `main`.
- Next planning focus should shift from baseline primitives to operator-ready UX and reliability evidence for real UI validation runs.

## Execution Progress

- [x] `p0-1-ui-e2e-readiness-and-smoke-pack` completed:
  - added one-command readiness target: `make ui-smoke`
  - added deterministic local smoke runner: `scripts/ui/local_ui_readiness_smoke.py`
  - added operator runbook doc: `docs/archive/operations/local-ui-readiness-smoke.md`
  - validated pass/fail remediation output for API boot, `/ui`, and Tool Manager -> Agent -> Playground first-turn flow
- [x] `p0-2-release-evidence-to-runtime-bridge` completed:
  - local smoke now exports runtime snapshots at `.local/ui-smoke-runtime-snapshots.json`
  - RC signoff evidence now includes advisory `Runtime Snapshots` section
  - normalized parser now exports `runtime_snapshots` payload in `.local/rc-signoff.json`
- [x] `p1-1-tool-manager-guided-onboarding` completed:
  - Tool Manager now includes a guided onboarding panel with step-by-step flow hints
  - added diagnostics panel with reason-code extraction + remediation suggestions
  - preserved existing backend API contracts; guidance is additive UI behavior
- [x] `p1-2-runtime-fairness-observability-surface` completed:
  - runtime control now exposes explicit fairness timeout indicators:
    - `fair_admission_timeout_total`
    - `tenant_fair_admission_timeout_total`
  - Playground now includes a fairness diagnostics panel backed by runtime-control stats
  - added deterministic API test coverage for fairness timeout counters under contention
- [x] `p2-1-long-run-multi-tenant-soak-suite` completed:
  - added opt-in non-blocking soak marker (`@pytest.mark.soak`) with `EXO_RUN_SOAK_TESTS=true` gate
  - added multi-tenant BYOC soak scenario combining budget windows, anomaly detection, and fair-admission contention
  - added deterministic starvation check and governance anomaly signal assertions
- [x] `p2-2-byoc-failure-injection-playbook` completed:
  - added operator playbook: `docs/operations/byoc-failure-injection-playbook.md`
  - mapped injected failure classes to runtime-control signals, evidence artifacts, and remediation commands
  - linked artifact-integrity dashboard and RC signoff checklist to playbook usage

## Proposed Execution Order (Approval Required)

### P0 (operator readiness first)

1. `p0-1-ui-e2e-readiness-and-smoke-pack`
   - Objective: make local UI validation deterministic and fast for manual operator testing.
   - Scope:
     - add one-command local readiness script/checklist for API + UI assets + baseline tenant setup
     - add deterministic smoke path for Tool Manager -> Agent -> Playground turn flow
   - Acceptance:
     - a documented local run path consistently gets from clean boot to working `/ui` test flow
     - smoke script/checklist catches missing prerequisites early with actionable output
   - Rollback/Fallback:
     - keep new readiness path additive; existing startup path remains unchanged

2. `p0-2-release-evidence-to-runtime-bridge`
   - Objective: bridge RC evidence artifacts with runtime control snapshots used in UI test sessions.
   - Scope:
     - export governance/runtime snapshots before and after local UI smoke
     - link those snapshots into `.local/rc-signoff.md` and normalized JSON as advisory attachments
   - Acceptance:
     - evidence artifact includes reproducible runtime snapshot references for local validation sessions
   - Rollback/Fallback:
     - advisory-only fields; signoff blocking behavior remains unchanged

### P1 (productization and UX confidence)

1. `p1-1-tool-manager-guided-onboarding`
   - Objective: reduce operator friction in first-time Tool Manager usage.
   - Scope:
     - add guided hints/inline diagnostics for import/upload/validate/version states
     - surface backend reason codes in user-friendly troubleshooting text
   - Acceptance:
     - UI/API integration tests cover guidance and reason-code rendering for common failure paths
   - Rollback/Fallback:
     - UI-only additive changes; backend contracts remain backward compatible

2. `p1-2-runtime-fairness-observability-surface`
   - Objective: expose fairness behavior clearly for operator triage.
   - Scope:
     - add explicit fairness counters/health summary in runtime-control and UI diagnostics panel
     - include fair-admission timeout and queue-contention indicators
   - Acceptance:
     - deterministic metrics are queryable per tenant and visible in UI diagnostics
   - Rollback/Fallback:
     - keep fairness policy optional and feature-flagged if observability surface is disabled

### P2 (scale and hardening extensions)

1. `p2-1-long-run-multi-tenant-soak-suite`
   - Objective: validate behavior under extended concurrent mixed-tenant workloads.
   - Scope:
     - add repeatable soak scenarios across budget windows, anomaly detectors, and fair admission
     - assert no starvation/regression under prolonged contention
   - Acceptance:
     - deterministic pass across repeated soak runs with bounded variance
   - Rollback/Fallback:
     - keep soak suite non-blocking behind explicit test marker until runtime is stabilized

2. `p2-2-byoc-failure-injection-playbook`
   - Objective: codify operator response for injected BYOC failures seen in local/CI simulation.
   - Scope:
     - add failure injection matrix + expected signals + recovery checklist
     - map each injected failure to runtime-control metrics and remediation actions
   - Acceptance:
     - runbook and evidence artifacts can be used to triage representative failure classes end-to-end
   - Rollback/Fallback:
     - docs/process only; no runtime behavior change required

## Global Acceptance Gates (for every slice)

- `python -m pytest -q`
- `python scripts/architecture/validate_layers.py`
- `python scripts/architecture/scan_forbidden_imports.py`
- `make ui-build`
- `make ui-verify`
- companion tracker synchronization:
  - `.local/index-and-planning/current/plan.md`
  - `.local/index-and-planning/current/work-tracker.md`

## Immediate Next Step

V3 execution queue is closed and validation handoff is complete.
Next implementation source: `docs/archive/plans/backlog-reconciliation-v4-execution-board.md`.
