<!--
File: docs-governance-baseline-map.md
Path: docs/plans/docs-governance-baseline-map.md
Role: Baseline classification of documentation paths used by active governance/workflow assets.
Used By:
 - docs/plans/documentation-cleanup-master-plan.md
 - docs/plans/docs-inventory-master.md
Depends On:
 - .cursor/rules/*.mdc
 - .cursor/skills/*.md
 - .agents/skills/*.md
 - scripts/pr/*.py
 - scripts/release/*.py
 - scripts/docs/check_docs_metadata.py
Notes:
 - This file is an execution baseline for archive migrations; update before each migration wave.
-->

# Docs Governance Baseline Map

## Scope

Governance reference scan over:

- `.cursor/rules/*.mdc`
- `.cursor/skills/*.md`
- `.agents/skills/*.md`
- `scripts/pr/*.py`
- `scripts/release/*.py`
- `scripts/docs/check_docs_metadata.py`

## Active Canonical (do not archive)

- `docs/plans/tenant-tool-execution-architecture.md`
- `docs/roadmap/alignment-audit-schema.md`
- `docs/operations/release-candidate-signoff-checklist.md`
- `docs/operations/byoc-artifact-integrity-dashboard.md`
- `docs/plans/docs-inventory-master.md`
- `docs/plans/docs-authority-map.md`
- `docs/README.md`
- `docs/plans/README.md`
- `docs/operations/README.md`
- `docs/modules/README.md`
- `docs/modules/core.md`
- `docs/modules/runtime.md`
- `docs/modules/tools.md`
- `docs/modules/policies.md`
- `docs/modules/api.md`
- `docs/modules/tenancy.md`

## Active Supporting (keep active but non-authoritative)

- `docs/plans/docs-archive-index.md`
- `docs/operations/documentation-maintenance-checklist.md`
- `docs/plans/documentation-cleanup-master-plan.md`
- `docs/plans/docs-and-notebooks-cleanup-plan.md`

## Archive Candidates (priority wave)

These were migrated to archive and remain non-authoritative:

- `docs/archive/plans/backlog-reconciliation-v2-execution-board.md`
- `docs/archive/plans/backlog-reconciliation-v3-execution-board.md`
- `docs/archive/plans/backlog-reconciliation-v3-execution-plan.md`
- `docs/archive/plans/backlog-reconciliation-v4-execution-board.md`
- `docs/archive/plans/p2-expansion-roadmap.md`
- `docs/archive/operations/local-ui-readiness-smoke.md`
- `docs/archive/results/audit_alignment_results.md`
- `docs/archive/results/audit_alignment_action_plan.md`

## Migration Guardrails

- Every moved file must include archive metadata (`Status`, `Canonical replacement`, `Archived on`, `Archive reason`).
- `docs/plans/docs-archive-index.md` must be updated in the same change set as each move.
- Active governance files must not point to `docs/archive/*` unless explicitly marked as historical context.
