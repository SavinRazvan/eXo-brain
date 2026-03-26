<!--
File: documentation-cleanup-master-plan.md
Path: docs/archive/plans/documentation-cleanup-master-plan.md
Role: Historical documentation cleanup execution plan (archived); anti-drift posture lives in inventory + authority + drift-prevention.
Used By:
 - docs/plans/docs-archive-index.md
 - Historical reference only
Depends On:
 - docs/plans/docs-inventory-master.md
 - docs/plans/docs-authority-map.md
 - docs/plans/docs-archive-index.md
Notes:
 - Planning and execution governance for docs only; does not define runtime behavior.
-->

# Documentation Cleanup Master Plan

## Status

- **`archived`** (superseded for active execution)
- Owner: Savin I. Razvan
- Last reviewed: 2026-03-11
- Archived on: 2026-03-25
- Canonical replacement: `docs/plans/docs-inventory-master.md`, `docs/plans/docs-authority-map.md`, `docs/governance/drift-prevention.md`
- Canonical current-state doc reference: `docs/plans/tenant-tool-execution-architecture.md`

## Goal

Keep repository documentation accurate, discoverable, and conflict-free by standardizing authority, indexing active docs, and archiving closed plan generations.

## Slices

1. **Authority and inventory freeze**
   - Create complete docs inventory with `active/planned/archived` status.
   - Define canonical source mapping and precedence.
2. **Canonical index and navigation**
   - Add docs indexes for top-level docs, plans, and operations.
   - Align root `README.md` links with canonical workflow docs.
3. **Historical rationalization**
   - Mark closed plan generations as archived and point to canonical replacements.
   - Publish archive index for traceability.
4. **Module documentation baseline**
   - Add `docs/modules/*` for P0 domains: core/runtime/tools/policies/api/tenancy.
5. **Contradiction cleanup**
   - Resolve stale UI-era and workflow contradictions.
6. **Drift prevention**
   - Add recurring maintenance checklist and review cadence.

## Acceptance Criteria

- Canonical docs are discoverable from root `README.md` in no more than two clicks.
- Closed plans are clearly archived and non-authoritative.
- P0 module docs exist and link to code/tests.
- PR workflow docs and operations docs do not conflict.

## Verification Gates

- `python -m pytest -q`
- `python scripts/architecture/validate_layers.py`
- `python scripts/architecture/scan_forbidden_imports.py`
- Documentation consistency review:
  - `README.md`
  - `.agents/skills/PR_WORKFLOW.md`
  - `.cursor/rules/pr-workflow-enforcement.mdc`
  - `docs/operations/release-candidate-signoff-checklist.md`
