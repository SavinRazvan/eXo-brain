---
name: merge-pr
description: Performs final merge readiness checks and merges only when review and prepare artifacts are complete and all required gates are green.
disable-model-invocation: true
---

# Merge PR

## Goal

Merge safely and deterministically after review and preparation are complete.

## Instructions

1. Verify required artifacts and readiness (pre-merge check):
   ```
   python scripts/pr/merge.py --pr <pr-number-or-url> \
     --actor "Savin I. Razvan" \
     --agents "review-pr | prepare-pr | merge-pr" \
     --check-only \
     [--arch-impacting]   # add for architecture-impacting PRs; enforces alignment artifact check
   ```
   - Script checks for `.local/review.md`, `.local/prep.md`, and (if `--arch-impacting`) `.local/alignment-audit.md`.
   - If the script exits non-zero, resolve blocking issues before proceeding.
2. Confirm no unresolved BLOCKER/IMPORTANT findings and no unresolved `P0` alignment findings.
3. Verify branch publication/linkage:
   - `python scripts/pr/verify_publish.py --branch <current-branch>`
   - `gh pr view --json headRefName,url,state`
4. Merge using repository policy:
   - `gh pr merge <pr-number> --merge --subject "<title>"`
5. Capture the merge commit SHA:
   - `gh pr view <pr-number> --json state,mergeCommit`
6. Finalize the merge artifact with the correct SHA (post-merge):
   ```
   python scripts/pr/merge.py --pr <pr-number-or-url> \
     --actor "Savin I. Razvan" \
     --agents "review-pr | prepare-pr | merge-pr" \
     --merge-sha <oid-from-step-5> \
     [--arch-impacting]
   ```
7. Enrich `.local/merge.md` with:
   - merge method
   - checks used as evidence
   - any follow-up issue/work item
   (the script already wrote attribution, branch stamp, preconditions, and merge SHA)
8. Finalize workflow (required close-out):
   - `git checkout main`
   - `python scripts/pr/finalize.py --branch <feature-branch>`
   - optional cleanup of other merged local branches:
     - `python scripts/pr/finalize.py --branch <feature-branch> --delete-merged-local`
   - confirm remote feature branch deletion (`git ls-remote --heads origin <feature-branch>` should return no output)
   - verify final repository state (`git status --short --branch`)

## No-Go Conditions

- missing prep/review artifacts (script will block with exit code 1)
- failing tests or architecture checks
- unresolved security or architecture boundary concerns
