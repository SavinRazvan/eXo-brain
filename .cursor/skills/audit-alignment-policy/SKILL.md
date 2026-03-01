---
name: audit-alignment-policy
description: Audits workflow/rule/skill consistency for deterministic-first, provider-neutral, and PR artifact requirements.
---

# Audit Alignment - Policy and Workflow

## Goal

Detect conflicts or gaps in governance instructions, workflow gates, and policy wording.

## Inputs

- `AGENTS.md`
- `.cursor/rules/*`
- `.agents/skills/PR_WORKFLOW.md`
- `.agents/skills/review-pr/SKILL.md`
- `.agents/skills/prepare-pr/SKILL.md`
- `.agents/skills/merge-pr/SKILL.md`
- `.cursor/skills/*` (for contradictory guidance)

## Checks

1. Deterministic-first guidance is consistent for state-changing/high-impact operations.
2. Provider-neutral constraints are consistent across rules and skills.
3. PR phase artifacts and attribution requirements are complete and consistent.
4. Required gates are consistently stated across all workflow docs.

## Output

Produce schema-constrained findings only, using categories:

- `policy_conflict`
- `workflow_gate_drift`
- `artifact_requirement_gap`
- `rule_parser_or_format_risk`
