---
name: test-module-coverage
description: Module-focused tests and coverage evidence for eXo-brain.
---

# Test module coverage

## When

`src/**` behavior change; coverage or regression requests; medium/high risk before merge.

## Procedure

1. Target modules/symbols; matrix: valid / boundary / invalid, lifecycle, failure/recovery.
2. Tests under `tests/modules/<module>/`.
3. Update `.local/index-and-planning/current/test-index.md` and `test-plan.md`; drop obsolete tests when contracts change.
4. Run: `pytest` scoped to module → broader as needed → `pytest --cov=src --cov-report=term-missing` for risky slices. Before merge path: **`python scripts/pr/check_testing_artifacts.py`** (see `scripts/pr/prepare.py` `GATES`).
5. Report: modules • edges added • gaps • tracker edits.

## Themes (when relevant)

Validation boundaries • error/reason codes • retry/replay on risky flows • async cleanup • policy negative paths.

## Output

`Coverage summary` → `Tests added/updated` → `Edge cases` → `Gaps` → `Index/plan updates` (paths in backticks).
