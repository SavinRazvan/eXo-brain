---
name: test-module-coverage
description: Designs and implements module-focused tests with edge cases and coverage evidence for eXo-brain.
---

# Test Module Coverage

## Goal

Improve confidence per module by adding/updating tests for:

- happy paths
- failure paths
- edge cases
- regression-prone behavior

while reporting clear test coverage outcomes.

## When To Use

- Any behavior change in `src/**`.
- User asks to improve coverage, test quality, or regression safety.
- Before merge when risk is medium/high or architecture-impacting.

## Procedure

1. Scope target modules and changed symbols.
2. Build a compact test matrix:
   - valid, boundary, and invalid inputs
   - state/lifecycle transitions
   - failure/recovery behavior
3. Add or update tests under `tests/modules/<module>/` with module-aligned naming.
4. Update persistent testing trackers:
   - `.local/control-center/test-index.md` (ownership, status, cleanup notes)
   - `.local/control-center/test-plan.md` (priorities and remaining gaps)
   - remove or rewrite obsolete tests when module behavior/contracts are removed or renamed
5. Run progressively:
   - targeted module suites first (`pytest -q tests/modules/<module>`)
   - broader suite when needed (`pytest -q`)
   - coverage evidence for medium/high-risk slices (`pytest --cov=src --cov-report=term-missing -q`)
6. Report:
   - modules covered
   - edge cases added
   - remaining gaps and next actions

## Required Test Coverage Themes

- input validation and boundary conditions
- error taxonomy and reason-code propagation where applicable
- retry/timeout/replay behavior for risky/state-changing flows
- async cleanup/shutdown behavior when relevant
- policy/authorization negative paths for guarded operations

## Output Contract

Return in this order:

1. `Coverage Summary`
2. `Tests Added/Updated`
3. `Edge Cases Covered`
4. `Remaining Gaps`
5. `Test Index/Plan Updates`

Use concise bullets and file paths in backticks.
