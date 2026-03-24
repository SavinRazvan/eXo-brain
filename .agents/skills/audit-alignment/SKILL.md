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
3. When deep module understanding is requested, run `.cursor/skills/audit-module-map/SKILL.md` first and carry forward its evidence.
4. Compare:
   - roadmap docs
   - research docs
   - implementation (`src`) + tests (`tests/modules`)
   - rules/skills/agents and `.local` artifact expectations
5. Write outputs:
   - `.local/workflow-artifacts/alignment/alignment-audit.md`
   - `.local/workflow-artifacts/alignment/alignment-todos.md`
6. Classify each finding:
   - `open`
   - `accepted_divergence`
   - `fixed`
   - `deferred`

## Exit Criteria

- Findings include file-based evidence and clear remediation.
- P0/P1 findings are explicitly surfaced before `/prepare-pr`.
