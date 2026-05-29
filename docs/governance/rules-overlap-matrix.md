<!--
File: rules-overlap-matrix.md
Path: docs/governance/rules-overlap-matrix.md
Role: Inventory of `.cursor/rules/*.mdc` overlaps and merge posture (Track D).
Used By:
 - Maintainers changing Cursor rules
Depends On:
 - AGENTS.md
 - docs/operations/agent-workflow-procedures.md
Notes:
 - Concise-pass + merge completed: `test-implementation-standard.mdc` merged into `implementation-workflow-governance.mdc`.
 - Last reviewed: 2026-05-29 — seven always-applied rules under `.cursor/rules/`.
-->

# Rules overlap matrix (Cursor)

| Rule file | Purpose | Overlap with | Posture |
|-----------|---------|--------------|---------|
| `provider-neutral-adapter-wall.mdc` | Adapter wall, layer boundaries | `AGENTS.md`, `docs/architecture/*` | **Keep separate** (never merge into workflow rules) |
| `pr-workflow-enforcement.mdc` | PR-first, artifacts, merge gates | `workflow-complete.md`, `PR_WORKFLOW.md` | **Short pointer** to `local_workflow_paths.py` + `prepare.py` |
| `implementation-workflow-governance.mdc` | Slice lifecycle, planning discipline, testing | `finish-slice` skill, `implementer.md` | **Keep** (absorbed former test-implementation standard) |
| `advisory-audit-alignment-enforcement.mdc` | Alignment artifacts (authored via `enterprise-auditor`) | `agent-workflow-procedures.md` | **Keep** |
| `commit-trailer-format.mdc` | Required commit trailers + optional `Assisted-by` (no `Made-with:`) | `README.md` (root), `AGENTS.md` § Commits, `docs/operations/local-workspace-layout.md`, `docs/plans/docs-authority-map.md`, `docs/plans/docs-inventory-master.md`, `docs/governance/workflow-source-owners.md`, `workflow-complete.md`, `release-candidate-signoff-checklist.md`, `docs/releases/RELEASE_TEMPLATE.md`, `configs/release/README.md`, `scripts/pr/README.md`, `scripts/pr/local_workflow_paths.py`, `eXo_adapters/` mirrors (if subtree tracked), `.local/.../agent-workflow-procedures.md` §3b | **Keep separate** |
| `file-docstring-header-relations.mdc` | File headers | All new source files | **Keep** |
| `local-artifact-protection.mdc` | `.exo_data/`, `.coverage` | ops runbooks | **Keep** |

## Track D status

- **D0 inventory:** this matrix.
- **D1 concise pass:** applied to always-applied rules (short invariants + links).
- **D2 merge/remove:** `test-implementation-standard.mdc` **removed** (content in `implementation-workflow-governance.mdc`).
