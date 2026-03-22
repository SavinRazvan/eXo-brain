<!--
File: docs-archive-index.md
Path: docs/plans/docs-archive-index.md
Role: Index of archived/historical plan and operations docs with canonical replacements.
Used By:
 - docs/README.md
 - docs/plans/README.md
 - docs/plans/docs-inventory-master.md
Depends On:
 - docs/plans/tenant-tool-execution-architecture.md
 - docs/operations/release-candidate-signoff-checklist.md
Notes:
 - Keep archived files for traceability; do not treat them as execution authority.
-->

# Documentation Archive Index

Archived docs are physically moved under `docs/archive/<domain>/` and are non-authoritative.
Use `docs/archive/README.md` for the archive metadata contract.

## Plan Archives

| Archived file | Canonical replacement |
|---|---|
| `docs/archive/plans/backlog-reconciliation-v2-execution-board.md` | `docs/plans/tenant-tool-execution-architecture.md` |
| `docs/archive/plans/backlog-reconciliation-v3-execution-board.md` | `docs/plans/tenant-tool-execution-architecture.md` |
| `docs/archive/plans/backlog-reconciliation-v3-execution-plan.md` | `docs/plans/tenant-tool-execution-architecture.md` |
| `docs/archive/plans/backlog-reconciliation-v4-execution-board.md` | `docs/plans/tenant-tool-execution-architecture.md` |
| `docs/archive/plans/p2-expansion-roadmap.md` | `docs/plans/tenant-tool-execution-architecture.md` |

## Operations Archives

| Archived file | Canonical replacement |
|---|---|
| `docs/archive/operations/local-ui-readiness-smoke.md` | `docs/operations/release-candidate-signoff-checklist.md` |

## Result Archives

| Archived file | Canonical replacement |
|---|---|
| `docs/archive/results/audit_alignment_results.md` | `.local/workflow-artifacts/alignment-audit.md` |
| `docs/archive/results/audit_alignment_action_plan.md` | `.local/workflow-artifacts/alignment-todos.md` |

## Historical but Useful Context

These remain useful historical references but are not execution authorities:

- `docs/plans/api-platform.md`
- `docs/plans/platform-extensions.md`

When they conflict with current execution status, use:

- `docs/plans/tenant-tool-execution-architecture.md`
- `docs/plans/option-c-contract-freeze.md`
- `docs/plans/option-c-worker-isolation-contract.md`
- `docs/plans/option-c-performance-gates.md`
