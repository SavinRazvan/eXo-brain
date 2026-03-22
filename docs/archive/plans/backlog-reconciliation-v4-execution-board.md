<!--
File: backlog-reconciliation-v4-execution-board.md
Path: docs/archive/plans/backlog-reconciliation-v4-execution-board.md
Role: Approval-ready execution board for post-v3 implementation planning.
Used By:
 - Maintainer implementation planning workflow
 - Future slice execution and PR packaging
Depends On:
 - docs/plans/tenant-tool-execution-architecture.md
 - docs/archive/plans/backlog-reconciliation-v3-execution-board.md
 - docs/archive/plans/p2-expansion-roadmap.md
 - .local/index-and-planning/current/plan.md
 - .local/index-and-planning/current/work-tracker.md
Notes:
 - This board is planning-only until explicitly approved for coding.
-->

# Backlog Reconciliation V4 Execution Board

> Status: Archived historical plan.
> Canonical replacement: `docs/plans/tenant-tool-execution-architecture.md`
> Archived on: 2026-03-19
> Archive reason: superseded

Date: 2026-03-05  
Actor: Savin I. Razvan  
Agent/s: gpt-5.3-codex

## Scope

Define the next approved queue after closure of:
- backlog reconciliation v3 execution queue
- full gates + local UI readiness smoke + RC signoff evidence handoff

## Current State Summary

- `docs/archive/plans/backlog-reconciliation-v3-execution-board.md` is closed.
- `docs/archive/plans/p2-expansion-roadmap.md` is closed.
- Runtime/evidence baseline is stable on `main` and release gates are green.
- Remaining work should focus on production hardening beyond baseline:
  - stronger governance evidence availability
  - adaptive autoscaling maturity
  - DLQ/replay and conflict operations depth
  - finer-grained tenancy/cost controls

## Execution Progress

- [x] `p0-1-governance-metrics-evidence-capture` baseline completed:
  - `scripts/ui/local_ui_readiness_smoke.py` now exports `.local/byoc-governance-metrics.json` during smoke flow.
  - local smoke server boot now enables BYOC runtime path for governance metrics availability (`EXO_ENABLE_BYOC_TOOL_RUNTIME=true` default for smoke process).
  - `make rc-signoff` governance section evaluates exported metrics when present (no longer defaulting to missing file path in smoke-driven runs).
- [x] `p0-2-soak-ci-nonblocking-lane` baseline completed:
  - added advisory workflow `.github/workflows/byoc-soak-nonblocking.yml` (nightly + manual dispatch).
  - workflow runs `pytest -m soak` with `EXO_RUN_SOAK_TESTS=true`, publishes logs/summaries, and remains non-blocking.
  - signoff checklist now references soak lane artifact outputs for triage.
- [x] `p1-1-agent-scaler-adaptive-controls` baseline completed:
  - `src/core/agent_scaler.py` now supports adaptive cooldown/hysteresis controls:
    - `scale_up_cooldown_evaluations`
    - `scale_up_hysteresis_backlog_delta`
  - scaler decisions now include deterministic diagnostics payload (`effective_scale_up_threshold`, `active_threshold`, cooldown fields).
  - `src/core/background_runtime.py` now records scaler decision diagnostics in job metadata and scale-up log context.
  - deterministic coverage extended in:
    - `tests/modules/core/test_agent_scaler.py`
    - `tests/modules/core/test_background_runtime_cancel_resume.py`
- [x] `p1-2-dlq-replay-operations-depth` baseline completed:
  - added bounded bulk DLQ replay API: `POST /tenants/{tenant_id}/admin/byoc/dlq/replay`
  - added deterministic replay summary schema:
    - attempted/replayed/failed counters
    - explicit per-job failure reason codes
  - extended BYOC adapter/runtime counters with `dlq_replay_failed_total`
  - deterministic API + adapter coverage updated in:
    - `tests/modules/api/test_byoc_runtime_control_api.py`
    - `tests/modules/tools/test_byoc_runtime.py`
- [x] `p1-3-conflict-observability-and-policy-coverage` baseline completed:
  - added structured conflict observability records (`strategy`, `tool_name`, `tool_version`, `reason_code`, `count`) in BYOC result stores:
    - `src/tools/byoc/result_store.py`
    - `src/tools/byoc/sqlite_store.py`
  - exposed tenant conflict counters in runtime-control stats and governance export:
    - `src/tools/byoc/connector_runtime.py`
    - `src/api/routers/runtime_control.py`
    - `src/api/schemas/runtime_control_schemas.py`
  - extended deterministic conflict policy coverage for edge combinations and export assertions:
    - `tests/modules/tools/test_byoc_result_conflict_resolution.py`
    - `tests/modules/api/test_byoc_runtime_control_api.py`
- [x] `p2-1-fine-grained-budget-governance` baseline completed:
  - extended BYOC cost-governance from tenant-wide window to optional partitioned enforcement (`per_tool` / `per_provider`) with deterministic fallback to tenant-wide policy when no partition match is configured.
  - added deterministic partition reason semantics:
    - `BYOC_COST_WINDOW_PARTITION_LIMIT_EXCEEDED`
    - `BYOC_COST_PARTITION_LIMIT_EXCEEDED`
  - extended runtime-control tenant metrics with partitioned cost counters/remaining budget fields while preserving existing tenant-wide totals.
  - deterministic coverage added for:
    - partitioned limit + reset behavior (`tests/modules/tools/test_byoc_runtime.py`)
    - cross-tenant isolation under provider partition limits (`tests/modules/api/test_byoc_runtime_control_api.py`)
- [x] `p2-2-ui-e2e-automation-lane` baseline completed:
  - added repeatable UI E2E lane wrapper `scripts/ui/ui_e2e_automation_lane.py` and `make ui-e2e-smoke` target that normalize Tool Manager + Playground smoke outcomes into deterministic artifacts.
  - added non-blocking CI workflow `.github/workflows/ui-e2e-nonblocking.yml` (nightly + manual) with advisory artifact upload for triage.
  - linked UI E2E advisory artifact into RC signoff evidence and parser output:
    - `scripts/release/rc_signoff.py` (`UI E2E Automation` section)
    - `scripts/release/parse_rc_signoff.py` (`ui_e2e_automation` payload)
  - added deterministic coverage for lane artifact generation and parser/report integration:
    - `tests/modules/unknown/test_ui_e2e_automation_lane.py`
    - `tests/modules/unknown/test_release_scripts.py`
- [x] `v4-queue-closure-and-ui-validation-handoff` completed:
  - V4 queue is formally closed after P0/P1/P2 baseline delivery.
  - Historical UI validation lane references are archived and treated as non-canonical for current delivery.
  - Canonical active track remains Option C API-first execution (control-plane + adapter-plane + hosted/BYOC data-plane).
  - Ongoing delivery gates continue under Option C runbook docs (`docs/plans/option-c-performance-gates.md`, `docs/plans/tenant-tool-execution-architecture.md`).

## Proposed Execution Order (Approval Required)

### P0 (release evidence and operational certainty)

1. `p0-1-governance-metrics-evidence-capture`
   - Objective: make governance alerts consistently evidence-backed during local signoff runs.
   - Scope:
     - ensure `.local/byoc-governance-metrics.json` is produced/linked during readiness/signoff flow
     - remove common `UNAVAILABLE` advisory path when runtime data is present
   - Acceptance:
     - `make rc-signoff` reports governance metrics as available during standard local smoke/signoff sequence
     - normalized JSON (`.local/rc-signoff.json`) contains deterministic non-null governance fields
   - Rollback/Fallback:
     - keep advisory behavior as fallback when metrics cannot be captured

2. `p0-2-soak-ci-nonblocking-lane`
   - Objective: continuously exercise long-run BYOC contention scenarios without blocking regular PR velocity.
   - Scope:
     - add non-blocking CI lane (scheduled or opt-in) for `EXO_RUN_SOAK_TESTS=true`
     - publish soak artifacts/logs for triage
   - Acceptance:
     - soak lane executes successfully and uploads evidence artifacts
     - main PR gates remain unchanged and deterministic
   - Rollback/Fallback:
     - disable soak lane via workflow flag if instability/noise appears

### P1 (runtime hardening beyond baseline)

1. `p1-1-agent-scaler-adaptive-controls`
   - Objective: evolve baseline scale-up/backpressure policy to adaptive behavior under sustained load.
   - Scope:
     - add cooldown/hysteresis-aware scaling policy signals
     - expose deterministic scaler diagnostics in runtime control stats
   - Acceptance:
     - tests validate scale recommendation stability across burst and recovery windows
     - no regression in current backpressure safety behavior
   - Rollback/Fallback:
     - keep current static-threshold baseline behind feature flag

2. `p1-2-dlq-replay-operations-depth`
   - Objective: improve operability of dead-letter queue replay at tenant scale.
   - Scope:
     - add bounded bulk replay controls and replay guardrails
     - add deterministic replay outcome summaries
   - Acceptance:
     - replay APIs support controlled multi-job replay with clear success/failure accounting
     - tests cover quota/lease/integrity failure cases during bulk replay
   - Rollback/Fallback:
     - preserve single-job replay as default path

3. `p1-3-conflict-observability-and-policy-coverage`
   - Objective: make result conflict behavior transparent and triage-ready.
   - Scope:
     - export conflict reason counters by strategy/tenant/tool/version
     - extend policy tests for edge conflict combinations
   - Acceptance:
     - runtime-control/governance export includes deterministic conflict telemetry fields
     - tests prove reject/replace outcomes remain strategy-consistent
   - Rollback/Fallback:
     - keep existing strategy resolution path unchanged when telemetry disabled

### P2 (advanced governance and rollout confidence)

1. `p2-1-fine-grained-budget-governance`
   - Objective: move from tenant-wide budget windows to optional finer controls.
   - Scope:
     - support configurable per-tool or per-provider budget partitions
     - preserve deterministic rejection reason semantics
   - Acceptance:
     - tests cover partitioned budget accounting and reset behavior
     - no cross-tenant leakage in counters or enforcement
   - Rollback/Fallback:
     - fallback to tenant-wide window policy mode

2. `p2-2-ui-e2e-automation-lane`
   - Objective: reduce manual-only risk in dashboard validation.
   - Scope:
     - add repeatable browser-based smoke automation for Tool Manager + Playground critical flows
     - link run outputs into RC evidence references as advisory attachments
   - Acceptance:
     - automation reproduces key local UI validation path and emits pass/fail artifacts
     - no dependency on external secrets for default local execution
   - Rollback/Fallback:
    - historical fallback referenced `make ui-smoke`; current API-first canonical release gate is `make rc-signoff`

## Global Acceptance Gates (for every slice)

- `python -m pytest -q`
- `python scripts/architecture/validate_layers.py`
- `python scripts/architecture/scan_forbidden_imports.py`
- Optional legacy UI gates (`make ui-build`, `make ui-verify`) apply only when a UI track is explicitly re-opened.
- companion tracker synchronization:
  - `.local/index-and-planning/current/plan.md`
  - `.local/index-and-planning/current/work-tracker.md`

## Immediate Next Step

Approval gate:
- approve `p0-1-governance-metrics-evidence-capture` to start coding on a focused implementation branch.
