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
2. If architecture-impacting scope, confirm advisory alignment artifacts exist:
   - `.local/alignment-audit.md`
   - `.local/alignment-todos.md`
   and ensure unresolved `P0` findings are fixed or explicitly accepted with rationale.
3. Apply focused fixes only within PR scope.
4. Run required gates:
   - `python -m pytest -q`
   - `python scripts/architecture/validate_layers.py`
   - `python scripts/architecture/scan_forbidden_imports.py`
5. Update tracking docs if implementation status changed:
   - `.cursor/research-for-refactor/12-bootstrap-checklist.md`
   - `.cursor/research-for-refactor/06-mvp-build-sequence.md`
6. Write `.local/prep.md` with:
   - resolved findings
   - verification output summary
   - current HEAD SHA
   - residual risks/follow-ups
   - initialize/update artifact with:
    - `python scripts/pr/prepare.py --pr <pr-number-or-url> --actor "Savin I. Razvan" --agents "review-pr | prepare-pr"`

## Exit Criteria

Status should be: `PR is ready for /merge-pr`.
