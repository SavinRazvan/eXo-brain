---
name: implementation-execution-loop
description: Runs disciplined implementation slices with mandatory control-center tracking, validation gates, and handoff reporting.
---

# Implementation Execution Loop

## Goal

Execute implementation work in high-quality, reversible slices while keeping the local control center accurate and current.

## When to Use

- Starting a new feature/fix/chore implementation task.
- Continuing an in-progress implementation slice.
- Recovering from blocked work where traceability must remain intact.

## Required Inputs

- `.local/control-center/plan.md`
- `.local/control-center/work-tracker.md`
- `.local/control-center/updates-log.md`
- `.local/control-center/architecture.md`
- Applicable architecture/rule docs in `.cursor/rules/*`

## Mandatory Steps

1. Read plan + tracker files before coding.
2. Select one focused slice and mark it `in_progress`.
3. Ensure acceptance criteria and rollback/fallback are documented.
4. Implement incrementally (contracts -> implementation -> tests).
5. Run required gates:
   - `python -m pytest -q` (or scoped tests with justification)
   - `python scripts/architecture/validate_layers.py`
   - `python scripts/architecture/scan_forbidden_imports.py`
6. Update trackers after execution:
   - status changes in `work-tracker.md`
   - summarized progress in `updates-log.md`
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
- updated tracker files
- outstanding blockers and next step
