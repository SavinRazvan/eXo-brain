---
name: audit-alignment
description: Maintainer advisory audit for cross-source alignment drift before preparation/merge on architecture-impacting PRs.
disable-model-invocation: true
---

# Audit Alignment (Maintainer)

## Goal

Provide advisory findings that reconcile roadmap, research, code/tests, and workflow governance before merge preparation.

## Instructions

1. Run in advisory-only mode; do not apply direct edits in this phase.
2. Use `docs/roadmap/alignment-audit-schema.md` for finding format and severity.
3. Compare:
   - roadmap docs
   - research docs
   - implementation (`src`) + tests (`tests/modules`)
   - rules/skills/agents and `.local` artifact expectations
4. Write outputs:
   - `.local/alignment-audit.md`
   - `.local/alignment-todos.md`
5. Classify each finding:
   - `open`
   - `accepted_divergence`
   - `fixed`
   - `deferred`

## Exit Criteria

- Findings include file-based evidence and clear remediation.
- P0/P1 findings are explicitly surfaced before `/prepare-pr`.
