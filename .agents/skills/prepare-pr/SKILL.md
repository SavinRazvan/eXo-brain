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
4. Run gates and create the prep artifact in one step:
   - `python scripts/pr/prepare.py --pr <pr-number-or-url> --actor "Savin I. Razvan" --agents "review-pr | prepare-pr"`
   - The script runs `pytest -q`, `validate_layers.py`, and `scan_forbidden_imports.py` internally and writes `.local/prep.md` with results.
   - If the script exits non-zero, fix the failing gate before proceeding.
   - If gates were already run and verified independently (e.g. as part of a prior step), pass `--skip-gates` to record them as externally verified without re-running.
5. Update tracking docs if implementation status changed:
   - `.cursor/research-for-refactor/12-bootstrap-checklist.md`
   - `.cursor/research-for-refactor/06-mvp-build-sequence.md`
6. Enrich `.local/prep.md` with:
   - resolved findings
   - residual risks/follow-ups
   (the script already wrote attribution, branch/HEAD stamp, and gate results)

## Exit Criteria

Status should be: `PR is ready for /merge-pr`.
