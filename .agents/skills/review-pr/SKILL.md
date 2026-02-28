---
name: review-pr
description: Reviews a pull request for correctness, architecture boundary safety, and test quality before any preparation or merge step. Use when evaluating a PR and producing findings.
disable-model-invocation: true
---

# Review PR

## Goal

Review-only phase that identifies issues and decides if the PR is ready for preparation.

## Instructions

1. Read PR context and changed files.
2. Focus findings on:
   - bugs/regressions
   - architecture boundary violations
   - security/safety risks
   - missing tests
3. Do not edit code in this phase.
4. Write findings to `.local/review.md`.
   - initialize/update artifact with:
     - `python scripts/pr/review.py --pr <pr-number-or-url> --actor <github_username>`
5. Add recommendation:
   - `READY FOR /prepare-pr`
   - `NEEDS WORK`
   - `NEEDS DISCUSSION`

## Minimum Review Checklist

- provider SDK isolation preserved (`runtime/*adapter*` only)
- core has no provider-name routing logic
- policy gates exist for state-changing/high-impact operations
- tests are sufficient for changed behavior
