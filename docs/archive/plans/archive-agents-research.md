<!--
File: archive-agents-research.md
Path: docs/archive/plans/archive-agents-research.md
Role: Tracks reusable testing/documentation agent assets discovered in _archive and migration decisions.
Used By:
 - docs/plans/docs-archive-index.md
Depends On:
 - _archive/.agents/skills/test-module-coverage/SKILL.md
 - _archive/.agents/skills/audit-module-docs-alignment/SKILL.md
 - _archive/.cursor/agents/test-runner.md
 - _archive/.cursor/agents/verifier.md
Notes:
 - Archived for traceability; advisory only. Promote assets only after compatibility and quality review.
-->

# Archive agents research

> Status: **Archived** (research snapshot).
> Canonical replacement: N/A — reference `.cursor/agents`, `.cursor/skills`, `.agents/skills` for current assets.
> Archived on: 2026-03-25
> Archive reason: historical snapshot

## Objective
- Reuse proven archive assets to accelerate module test and docs automation in this repository.

## Candidate assets
- `_archive/.agents/skills/test-module-coverage/SKILL.md`
- `_archive/.agents/skills/audit-module-docs-alignment/SKILL.md`
- `_archive/.cursor/agents/test-runner.md`
- `_archive/.cursor/agents/verifier.md`

## Evaluation criteria
- Fits current repo boundaries and workflows.
- Produces deterministic, evidence-backed output.
- Does not bypass policy/rule gates.
- Keeps advisory/remediation responsibilities clearly separated.

## Planned outputs
- `module-testing-agent` definition (coverage-oriented, module-aware).
- `module-docs-agent` definition (docs drift and completeness).
- Migration note: archive origin -> adapted local behavior -> acceptance tests.

## Status
- `planned` inventory complete, extraction and adaptation pending.
