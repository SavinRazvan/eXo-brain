---
name: merge-pr
description: Performs final merge readiness checks and merges only when review and prepare artifacts are complete and all required gates are green.
disable-model-invocation: true
---

# Merge PR

## Goal

Merge safely and deterministically after review and preparation are complete.

## Instructions

1. Verify required artifacts exist:
   - `.local/review.md`
   - `.local/prep.md`
   - `.local/alignment-audit.md` and `.local/alignment-todos.md` for architecture-impacting PRs
2. Verify all required gates are green.
3. Verify branch publication/linkage:
   - `python scripts/pr/verify_publish.py --branch <current-branch>`
   - `gh pr view --json headRefName,url,state`
4. Confirm no unresolved BLOCKER/IMPORTANT findings and no unresolved `P0` alignment findings.
5. Merge using repository policy.
6. Record merge summary in `.local/merge.md`:
   - merge method
   - merge SHA
   - checks used as evidence
   - any follow-up issue/work item
   - initialize/update artifact with:
     - `python scripts/pr/merge.py --pr <pr-number-or-url> --actor <github_username>`
7. Finalize workflow (required close-out):
   - `git checkout main`
   - `git pull --ff-only origin main`
   - delete local feature branch if present (`git branch -d <feature-branch>`)
   - confirm remote feature branch deletion
   - verify final repository state on `main`

## No-Go Conditions

- missing prep/review artifacts
- failing tests or architecture checks
- unresolved security or architecture boundary concerns
