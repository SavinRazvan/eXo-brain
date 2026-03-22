<!--
File: archive-agents-research.md
Path: docs/plans/archive-agents-research.md
Role: Tracks reusable testing/documentation agent assets discovered in _archive and migration decisions.
Used By:
 - Planning for test/docs automation agents
Depends On:
 - _archive/.agents/skills/test-module-coverage/SKILL.md
 - _archive/.agents/skills/audit-module-docs-alignment/SKILL.md
 - _archive/.cursor/agents/test-runner.md
 - _archive/.cursor/agents/verifier.md
Notes:
 - Keep this advisory first. Promote assets only after compatibility and quality review.
-->

# Archive agents research

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
