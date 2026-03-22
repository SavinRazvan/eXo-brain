---
name: implementation-execution-loop
description: Runs disciplined implementation slices with mandatory index-and-planning tracking, validation gates, and handoff reporting.
---

# Implementation Execution Loop

## Goal

Execute implementation work in high-quality, reversible slices while keeping the local control center accurate and current.

## When to Use

- Starting a new feature/fix/chore implementation task.
- Continuing an in-progress implementation slice.
- Recovering from blocked work where traceability must remain intact.

## Required Inputs

- `.local/index-and-planning/current/plan.md` (includes **Implementer slice closure**)
- `.local/index-and-planning/current/work-tracker.md`
- `.local/index-and-planning/history/updates-log.md`
- `docs/architecture/workspace-architecture.md` (local stub may live under `.local/.../current/architecture.md`)
- `.local/index-and-planning/current/test-plan.md` and `.local/index-and-planning/current/test-index.md` when the slice touches tests or ownership
- `docs/operations/workflow-complete.md` section **F** for the full handoff checklist
- Applicable architecture/rule docs in `.cursor/rules/*`

## Mandatory Steps

1. Read plan + tracker files before coding.
2. Select one focused slice and mark it `in_progress`.
3. Ensure acceptance criteria and rollback/fallback are documented.
4. Implement incrementally (contracts -> implementation -> tests).
5. Run required gates (same order as `scripts/pr/prepare.py` `GATES`; see `docs/operations/workflow-complete.md` §A):
   - `python scripts/pr/check_testing_artifacts.py`
   - `python -m pytest -q` (or scoped tests with justification)
   - `python scripts/architecture/validate_layers.py`
   - `python scripts/architecture/scan_forbidden_imports.py`
   - `python scripts/architecture/check_governance_consistency.py` when governance/workflows/policy docs changed
6. Close the implementer loop after execution (canonical checklist: `.local/index-and-planning/current/plan.md` **Implementer slice closure** + `docs/operations/workflow-complete.md` section **F**):
   - `work-tracker.md` status changes (one primary `in_progress` at a time)
   - `updates-log.md` summarized progress (no repeated prepare-gate blocks — `agent-workflow-procedures.md`)
   - `test-plan.md` / `test-index.md` when tests or ownership changed
   - `coverage-index.md` via `coverage json` + `scripts/dev/generate_coverage_index.py` when coverage was run for the slice
   - `.local/agents-control-center/config/pages.json` + dashboard header **Depends On** when new tracker paths appear or Coverage tab must match `current/coverage-index.md`
   - do **not** edit `.local/agents-control-center/audits/module-audit.html` unless refreshing a deliberate audit export
7. Emit handoff with:
   - what changed
   - validation outcomes
   - blockers/risks
   - next action

## Quality Requirements

- Preserve provider-neutral architecture boundaries.
- Include failure-path and retry/timeout tests when relevant.
- Keep changes small, reversible, and evidence-backed.
- Do not leave tracker files stale after code changes.

## Output Contract

At completion, provide:
- slice name
- changed files/modules
- gates run + outcomes
- updated tracker files (explicit list, including `coverage-index.md` / HTML if touched)
- outstanding blockers and next step
