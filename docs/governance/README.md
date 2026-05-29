<!--
File: README.md
Path: docs/governance/README.md
Role: Index for documentation governance, IA charters, and workflow source-of-truth map.
Used By:
 - docs/README.md
 - docs/plans/docs-authority-map.md
Depends On:
 - docs/plans/docs-inventory-master.md
 - docs/governance/folder-charter.md
Notes:
 - Last reviewed: 2026-05-29
-->

# Governance documentation

**Status:** active  
**Owner:** Savin I. Razvan

This folder defines **where docs live**, **who owns workflow truth** (scripts vs prose), and **how to prevent drift** between rules, skills, operations runbooks, and implementation.

## Reading order

| Order | Document | When to use |
|---|---|---|
| 1 | [folder-charter.md](folder-charter.md) | “Does this belong in `docs/` or `.local/`?” |
| 2 | [docs-authority-map.md](../plans/docs-authority-map.md) | Two docs conflict — which wins? |
| 3 | [workflow-source-owners.md](workflow-source-owners.md) | PR gates, artifact paths, commit trailers |
| 4 | [drift-prevention.md](drift-prevention.md) | After changing gates, layout, or policy |
| 5 | [path-migration-map.md](path-migration-map.md) | Legacy → nested `.local/` paths (migration reference) |
| 6 | [rules-overlap-matrix.md](rules-overlap-matrix.md) | Editing `.cursor/rules/*.mdc` |
| 7 | [rollout-phases.md](rollout-phases.md) | Historical IA rollout (completed baseline) |

## Document index

| File | Role |
|---|---|
| [folder-charter.md](folder-charter.md) | `docs/` subtree purposes vs `.local/` operating workspace |
| [workflow-source-owners.md](workflow-source-owners.md) | Canonical owners: `prepare.py`, `local_workflow_paths.py`, rules, skills |
| [drift-prevention.md](drift-prevention.md) | Checklists after gate, lifecycle, layout, or trailer changes |
| [path-migration-map.md](path-migration-map.md) | Old → new path map; pairs with `migrate_local_workspace_layout.py` |
| [rules-overlap-matrix.md](rules-overlap-matrix.md) | Cursor rules inventory and merge posture (Track D) |
| [rollout-phases.md](rollout-phases.md) | Completed docs/local IA rollout phases |

## Related (outside this folder)

| Area | Entry |
|---|---|
| Doc inventory & status | [docs-inventory-master.md](../plans/docs-inventory-master.md) |
| Maintainer PR checklist | [workflow-complete.md](../operations/workflow-complete.md) |
| `.local/` layout contract | [local-workspace-layout.md](../operations/local-workspace-layout.md) |
| PR artifact maintenance | [documentation-maintenance-checklist.md](../operations/documentation-maintenance-checklist.md) |
| Alignment audit schema | [roadmap/alignment-audit-schema.md](../roadmap/alignment-audit-schema.md) |
| Architecture-impacting audits | `enterprise-auditor` + [enterprise-architecture-audit/SKILL.md](../../.cursor/skills/enterprise-architecture-audit/SKILL.md) |

## Product vocabulary (strategy alignment)

When docs mention **control plane**, **customer bridge**, **provider runtime adapter**, or monetization on **governance** (not raw LLM resale), keep language aligned with:

- [docs/strategy/README.md](../strategy/README.md)
- [governed-execution-positioning.md](../strategy/governed-execution-positioning.md)
- [control-plane-product-alignment-plan.md](../plans/control-plane-product-alignment-plan.md)
- [traceability-matrix.md](../strategy/traceability-matrix.md)
- [customer-api-integration-guide.md](../api/customer-api-integration-guide.md) (v1.9+, `/tenants/...` paths)

Architecture: [ARCHITECTURE.md](../architecture/ARCHITECTURE.md), [workspace-architecture.md](../architecture/workspace-architecture.md).

## Quick commands

```bash
python scripts/architecture/check_governance_consistency.py   # rules/skills/merge parity
python scripts/docs/check_docs_metadata.py                    # P0 module doc sections
python scripts/dev/migrate_local_workspace_layout.py --dry-run  # .local/ layout check
```
