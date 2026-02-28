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
2. Verify all required gates are green.
3. Confirm no unresolved BLOCKER/IMPORTANT findings.
4. Merge using repository policy.
5. Record merge summary in `.local/merge.md`:
   - merge method
   - merge SHA
   - checks used as evidence
   - any follow-up issue/work item

## No-Go Conditions

- missing prep/review artifacts
- failing tests or architecture checks
- unresolved security or architecture boundary concerns
