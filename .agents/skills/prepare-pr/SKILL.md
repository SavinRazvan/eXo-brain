---
name: prepare-pr
description: Prepares a pull request for merge by applying approved fixes, running required gates, and updating checklists/docs with evidence. Use after review-pr recommends proceeding.
disable-model-invocation: true
---

# Prepare PR

## Goal

Make the PR merge-ready with validated fixes and explicit evidence.

## Instructions

1. Confirm `.local/review.md` exists and resolve BLOCKER/IMPORTANT findings first.
2. Apply focused fixes only within PR scope.
3. Run required gates:
   - `python -m pytest -q`
   - `python scripts/architecture/validate_layers.py`
   - `python scripts/architecture/scan_forbidden_imports.py`
4. Update tracking docs if implementation status changed:
   - `.cursor/research-for-refactor/12-bootstrap-checklist.md`
   - `.cursor/research-for-refactor/06-mvp-build-sequence.md`
5. Write `.local/prep.md` with:
   - resolved findings
   - verification output summary
   - current HEAD SHA
   - residual risks/follow-ups

## Exit Criteria

Status should be: `PR is ready for /merge-pr`.
