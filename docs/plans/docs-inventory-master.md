<!--
File: docs-inventory-master.md
Path: docs/plans/docs-inventory-master.md
Role: Master inventory of repository documentation with lifecycle status and canonical pointers.
Used By:
 - docs/plans/documentation-cleanup-master-plan.md
 - docs/plans/docs-authority-map.md
Depends On:
 - docs/README.md
 - docs/plans/README.md
Notes:
 - Inventory should be updated whenever docs status changes.
-->

# Documentation Inventory (Master)

## Active Canonical

| Path | Role |
|---|---|
| `README.md` | Project entrypoint and developer quick-start |
| `docs/api/customer-api-integration-guide.md` | Tier-aware API contract documentation for customer onboarding (chat/agents/workflow + governance ingress) |
| `docs/architecture_mvp.md` | Layer architecture and design intent |
| `docs/runtime_contracts.md` | Runtime adapter contract and behavior |
| `docs/mcp_integration.md` | MCP integration boundaries |
| `docs/plugin_lifecycle.md` | Plugin lifecycle contract |
| `docs/workflow_loading.md` | Workflow loading semantics |
| `docs/plans/tenant-tool-execution-architecture.md` | Canonical current implementation status and execution architecture |
| `docs/plans/option-c-contract-freeze.md` | Option C contract freeze source |
| `docs/plans/option-c-worker-isolation-contract.md` | Option C worker isolation contract |
| `docs/plans/option-c-performance-gates.md` | Option C performance/SLO gate definitions |
| `docs/operations/release-candidate-signoff-checklist.md` | Canonical release signoff process |
| `docs/operations/byoc-failure-injection-playbook.md` | BYOC failure drills |
| `docs/operations/byoc-artifact-integrity-dashboard.md` | BYOC integrity operations guidance |

## Planned / Working

| Path | Role |
|---|---|
| `docs/plans/documentation-cleanup-master-plan.md` | Canonical documentation cleanup execution plan |
| `docs/plans/docs-inventory-master.md` | Lifecycle inventory and classification table |
| `docs/plans/docs-authority-map.md` | Authority and precedence map for docs |
| `docs/plans/docs-archive-index.md` | Archive index and replacement mapping |
| `docs/plans/docs-governance-baseline-map.md` | Governance dependency baseline for archive migrations |
| `docs/plans/docs-and-notebooks-cleanup-plan.md` | Notebook/doc cleanup execution history and references |
| `docs/plans/notebook-standards.md` | Notebook standards and ownership |

## Archived / Historical

| Path | Replacement |
|---|---|
| `docs/archive/plans/backlog-reconciliation-v2-execution-board.md` | `docs/plans/tenant-tool-execution-architecture.md` |
| `docs/archive/plans/backlog-reconciliation-v3-execution-board.md` | `docs/plans/tenant-tool-execution-architecture.md` |
| `docs/archive/plans/backlog-reconciliation-v3-execution-plan.md` | `docs/plans/tenant-tool-execution-architecture.md` |
| `docs/archive/plans/backlog-reconciliation-v4-execution-board.md` | `docs/plans/tenant-tool-execution-architecture.md` |
| `docs/archive/plans/p2-expansion-roadmap.md` | `docs/plans/tenant-tool-execution-architecture.md` |
| `docs/archive/operations/local-ui-readiness-smoke.md` | `docs/operations/release-candidate-signoff-checklist.md` |
| `docs/archive/results/audit_alignment_results.md` | `.local/alignment-audit.md` |
| `docs/archive/results/audit_alignment_action_plan.md` | `.local/alignment-todos.md` |

## Notes

- `docs/archive/*` contains non-authoritative historical documents with replacement pointers.
- `.local/*` artifacts are execution evidence snapshots and not long-lived canonical docs.
