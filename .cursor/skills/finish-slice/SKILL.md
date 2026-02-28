---
name: finish-slice
description: Finalizes a development slice safely by running checks, syncing docs/checklists, and preparing merge-ready evidence. Use when wrapping up a feature/fix/chore or before commit/PR.
---

# Finish Slice

## When to Use

- User asks to finalize current work.
- User asks for commit/PR readiness.
- Need to verify safety/quality before merge.

## Instructions

1. Verify scope completeness:
   - changed files match intended slice
   - no unrelated edits included
2. Run required verification:
   - test suite (or targeted tests)
   - architecture boundary checks
3. Confirm implementation evidence:
   - failure paths covered where relevant
   - observability/audit fields present for state-changing paths
4. Sync project tracking docs:
   - update checklist statuses
   - update MVP sequence status if scope changed
5. Prepare merge-ready output:
   - concise summary
   - verification results
   - remaining risks / next steps
6. If user requests commit:
   - craft clean commit message based on repo style
   - include required trailer format from project policy

## Output Template

```markdown
Slice complete: <yes/no>
Checks:
- tests: <result>
- architecture: <result>
Docs synced: <files>
Ready for commit/PR: <yes/no>
Next:
- <next slice>
```
