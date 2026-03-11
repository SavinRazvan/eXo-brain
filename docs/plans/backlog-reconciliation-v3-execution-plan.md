<!--
File: backlog-reconciliation-v3-execution-plan.md
Path: docs/plans/backlog-reconciliation-v3-execution-plan.md
Role: Actionable execution plan for implementing backlog reconciliation v3 board.
Used By:
 - Maintainer implementation workflow
 - Slice-by-slice PR execution
Depends On:
 - docs/plans/backlog-reconciliation-v3-execution-board.md
 - docs/operations/release-candidate-signoff-checklist.md
Notes:
 - This plan operationalizes v3 board items into executable slices.
-->

# Backlog Reconciliation V3 Execution Plan

> Status: Archived historical plan.
> Canonical replacement: `docs/plans/tenant-tool-execution-architecture.md`

Date: 2026-03-05  
Actor: Savin I. Razvan  
Agent/s: gpt-5.3-codex

## Goal

Execute the v3 board in a deterministic order that improves real-world operator confidence before your browser UI validation sessions, then scales into long-run reliability hardening.

Primary outcomes:
- repeatable local run path for UI testing
- stronger runtime/evidence observability during manual validation
- production-safe UX and fairness diagnostics
- repeatable scale/failure drills with clear runbooks

## Execution Order

1. `p0-1-ui-e2e-readiness-and-smoke-pack`
2. `p0-2-release-evidence-to-runtime-bridge`
3. `p1-1-tool-manager-guided-onboarding`
4. `p1-2-runtime-fairness-observability-surface`
5. `p2-1-long-run-multi-tenant-soak-suite`
6. `p2-2-byoc-failure-injection-playbook`

## Slice Playbook

### Slice 1: `p0-1-ui-e2e-readiness-and-smoke-pack`

Objective:
- make one-command local startup and UI smoke validation deterministic.

Scope:
- add a local readiness script/checklist under `scripts/` + `docs/operations/`
- verify API boot, `/ui` availability, and first-turn smoke path
- ensure clear error messages for missing prerequisites/env setup

Acceptance:
- one documented command sequence consistently reaches a working UI smoke path
- smoke output includes pass/fail per stage with actionable remediation

Rollback/Fallback:
- keep readiness helpers additive only; do not alter baseline startup behavior

Delivered evidence:
- `Makefile` (`ui-smoke` target)
- `scripts/ui/local_ui_readiness_smoke.py`
- `docs/operations/local-ui-readiness-smoke.md`
- local validation command: `make ui-smoke`

---

### Slice 2: `p0-2-release-evidence-to-runtime-bridge`

Objective:
- tie local UI smoke runs to reproducible runtime/evidence artifacts.

Scope:
- capture runtime-control snapshots before/after smoke execution
- include snapshot references in RC evidence as advisory fields
- keep parser compatibility for existing evidence consumers

Acceptance:
- generated evidence links smoke session context to runtime state snapshots
- no blocking behavior changes to existing signoff gates

Rollback/Fallback:
- advisory-only metadata; if unavailable, signoff format still parses cleanly

Delivered evidence:
- `scripts/ui/local_ui_readiness_smoke.py` (writes `.local/ui-smoke-runtime-snapshots.json`)
- `scripts/release/rc_signoff.py` (`Runtime Snapshots` advisory section)
- `scripts/release/parse_rc_signoff.py` (`runtime_snapshots` normalized JSON block)
- `tests/modules/unknown/test_release_scripts.py` coverage for section parsing/rendering

---

### Slice 3: `p1-1-tool-manager-guided-onboarding`

Objective:
- reduce friction in first-time Tool Manager setup and troubleshooting.

Scope:
- inline guidance/hints for import/upload/validate/version states
- present backend reason codes with user-facing remediation tips
- preserve existing API contracts

Acceptance:
- UI/API tests cover expected guidance for happy path and common failures
- operator can complete first tool flow without backend knowledge

Rollback/Fallback:
- UI-only additive behavior; backend semantics unchanged

Delivered evidence:
- `ui/src/screens/tools.ts` guided flow steps + diagnostics rendering + reason-code remediation mapping
- `ui/dist/index.html` onboarding and diagnostics sections for Tool Manager
- `ui/dist/styles.css` onboarding/diagnostics visual states
- `tests/modules/api/test_ui_static.py` coverage for onboarding and diagnostics surface presence

---

### Slice 4: `p1-2-runtime-fairness-observability-surface`

Objective:
- make fairness behavior and contention signals visible during operations.

Scope:
- surface fairness counters and timeout indicators in runtime control output
- expose a simple UI diagnostics view for fairness state
- keep fairness policy feature-gated

Acceptance:
- fairness indicators are queryable per tenant and reflected in diagnostics
- tests validate deterministic field shape and values

Rollback/Fallback:
- if UI surface is disabled, backend fairness feature remains optional

Delivered evidence:
- `src/tools/byoc/connector_runtime.py` fairness timeout indicators in control stats
- `ui/src/screens/playground.ts` fairness diagnostics refresh/render via runtime-control
- `ui/dist/index.html` fairness diagnostics panel in Playground
- `tests/modules/api/test_byoc_runtime_control_api.py` deterministic fairness timeout counter coverage
- `tests/modules/api/test_ui_static.py` diagnostics UI surface coverage

---

### Slice 5: `p2-1-long-run-multi-tenant-soak-suite`

Objective:
- prove no starvation/regression under prolonged contention.

Scope:
- add soak scenarios combining budgets, anomaly detectors, fairness controls
- provide repeatable markers/config for local and CI soak runs

Acceptance:
- repeated soak runs pass deterministically within defined variance bounds
- failures emit clear diagnostics and reproducible seeds/config

Rollback/Fallback:
- gate as non-blocking marker until runtime stabilizes fully

Delivered evidence:
- `tests/modules/api/test_byoc_soak_suite.py` opt-in soak scenario across tenants (`EXO_RUN_SOAK_TESTS=true`)
- `pytest.ini` soak marker registration (`soak`)
- deterministic assertions for:
  - no tenant starvation under fair-admission contention
  - fairness counters present in runtime-control stats
  - governance anomaly signal emission under stress/rejection pressure

---

### Slice 6: `p2-2-byoc-failure-injection-playbook`

Objective:
- codify incident response for injected BYOC failures.

Scope:
- define failure classes, expected signals, and operator actions
- map runtime-control metrics and evidence artifacts to each failure class

Acceptance:
- operators can run and triage representative injected failures end-to-end
- runbook links directly to evidence artifacts and remediation commands

Rollback/Fallback:
- docs/process only; runtime behavior unaffected

Delivered evidence:
- `docs/operations/byoc-failure-injection-playbook.md` failure matrix + triage procedure
- `docs/operations/byoc-artifact-integrity-dashboard.md` runbook linkage to failure-injection playbook
- `docs/operations/release-candidate-signoff-checklist.md` operator checklist hook for drill usage on anomaly/rejection signals

## Standard Gates (each slice)

- `python -m pytest -q`
- `python scripts/architecture/validate_layers.py`
- `python scripts/architecture/scan_forbidden_imports.py`
- `make ui-build`
- `make ui-verify`
- companion tracker updates:
  - `.cursor/research-for-refactor/06-mvp-build-sequence.md`
  - `.cursor/research-for-refactor/12-bootstrap-checklist.md`

## PR Workflow Per Slice

- create focused branch (`feature/<slice>`)
- implement + test + docs sync
- open PR and verify publish linkage
- run review/prepare/merge artifacts
- merge and sync `main`

## Immediate Next Action

V3 queue closure gates and browser UI validation handoff are complete.

Next implementation source:
- `docs/plans/backlog-reconciliation-v4-execution-board.md`
