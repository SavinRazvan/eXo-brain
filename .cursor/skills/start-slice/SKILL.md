---
name: start-slice
description: Starts a safe implementation slice by creating a branch, mapping checklist scope, and defining acceptance gates. Use when beginning new work, asking what to do next, or preparing a new feature/fix/chore.
---

# Start Slice

## When to Use

- User wants to begin a new implementation step.
- User asks what to do next and requests execution.
- Work needs clean branch + scope + acceptance criteria before coding.

## Instructions

1. Confirm slice scope from project checklist/docs:
   - `.cursor/research-for-refactor/12-bootstrap-checklist.md`
   - `.cursor/research-for-refactor/06-mvp-build-sequence.md`
2. Propose a branch name based on scope:
   - `feature/<scope>`, `fix/<scope>`, or `chore/<scope>`
3. Ensure branch safety:
   - do not start on `main`
   - keep branch focused on one slice
4. Define acceptance gates before code:
   - tests required
   - architecture checks required
   - rollback/fallback behavior
5. Start implementation incrementally:
   - interfaces/contracts first
   - implementation
   - tests
   - evidence
   - docs/checklist update

## Output Template

Use this concise structure:

```markdown
Slice: <name>
Branch: <feature/fix/chore-...>
Scope: <files/modules>
Acceptance:
- <test gate>
- <architecture gate>
- <rollback/fallback>
```
