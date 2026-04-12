<!--
File: docs-inventory-master.md
Path: docs/plans/docs-inventory-master.md
Role: Master inventory of repository documentation with lifecycle status and canonical pointers.
Used By:
 - docs/plans/docs-authority-map.md
 - docs/plans/docs-archive-index.md
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
| `docs/README.md` | Top-level documentation index (reading spine, module/API/plan pointers) |
| `docs/api/customer-api-integration-guide.md` | Tier-aware API contract documentation for customer onboarding (chat/agents/workflow + governance ingress) |
| `docs/api/governance-preview-and-testing.md` | Self-serve governance testing patterns, feedback loop, planned simulation/dry-run APIs |
| `docs/strategy/customer-self-serve-governance-journey.md` | Canonical customer self-serve governance product contract and implementer checklist |
| `docs/strategy/foundation-tier-adoption-checklist.md` | Foundation-tier API adoption steps with Pro/Enterprise deltas |
| `docs/plans/governance-configuration-reference-model.md` | Unified configuration entity model, dependency order, precedence, thin-UI mapping |
| `docs/operations/governance-reason-code-catalog.md` | Reason-code ownership and discovery process (not a full literal catalog) |
| `docs/architecture/beginner-workflow.md` | Beginner-friendly plain-language walkthrough of the platform workflow |
| `docs/architecture/mvp.md` | Layer architecture and design intent (canonical) |
| `docs/architecture_mvp.md` | Redirect stub → `docs/architecture/mvp.md` |
| `docs/architecture/workspace-architecture.md` | Workspace doctrine (adapters, policy, enterprise controls) |
| `docs/architecture/ARCHITECTURE.md` | Consolidated map: planes, Option C/strategy vocabulary, mermaid A–C, layers, modules, plans × concerns, maintainer checklist §14 |
| `docs/strategy/README.md` | Strategy package index (product direction, entitlements, traceability) |
| `docs/strategy/governed-execution-positioning.md` | Product boundary, ICP, monetization posture, and messaging guardrails for governed execution |
| `docs/operations/workflow-complete.md` | Maintainer workflow checklist (durable) |
| `docs/operations/agent-workflow-procedures.md` | Audit/PR dedup procedures; **§3b** git commit vs PR artifact provenance sync list |
| `docs/operations/local-workspace-layout.md` | Gitignored `.local/` layout; git trailers vs `.local/workflow-artifacts/pr/*` |
| `docs/operations/documentation-maintenance-checklist.md` | Maintainer checklist when architecture, API, tenancy, or workflow docs change |
| `docs/operations/logging-and-errors.md` | Logging rollout plan |
| `docs/governance/folder-charter.md` | `docs/` vs `.local/` charter |
| `docs/governance/path-migration-map.md` | Old → new path map |
| `docs/governance/workflow-source-owners.md` | Script-first ownership map |
| `docs/governance/drift-prevention.md` | Lightweight drift process |
| `docs/governance/rollout-phases.md` | IA rollout phase notes |
| `docs/governance/rules-overlap-matrix.md` | Cursor rules inventory / Track D |
| `docs/runtime_contracts.md` | Runtime adapter contract and behavior |
| `docs/mcp_integration.md` | MCP integration boundaries |
| `docs/plugin_lifecycle.md` | Plugin lifecycle contract |
| `docs/workflow_loading.md` | Workflow loading semantics |
| `docs/plans/tenant-tool-execution-architecture.md` | Canonical current implementation status and execution architecture |
| `docs/plans/option-c-contract-freeze.md` | Option C contract freeze source |
| `docs/plans/option-c-worker-isolation-contract.md` | Option C worker isolation contract |
| `docs/plans/option-c-performance-gates.md` | Option C performance/SLO gate definitions |
| `docs/operations/release-candidate-signoff-checklist.md` | Canonical release signoff process |
| `docs/releases/RELEASE_TEMPLATE.md` | Release / rollout note template (RC vs git trailer disclosure) |
| `configs/release/README.md` | Release gate config bundle index (`configs/release/*.yaml` + JSON); git vs RC evidence |
| `scripts/pr/README.md` | PR workflow scripts hub (artifact paths vs **commit-trailer-format.mdc**) |
| `docs/operations/byoc-failure-injection-playbook.md` | BYOC failure drills |
| `docs/operations/byoc-artifact-integrity-dashboard.md` | BYOC integrity operations guidance |
| `docs/plans/short-long-term-execution-plan.md` | Short vs long execution horizons; companion to `next-directions.md` Tier emphasis |
| `docs/plans/short-long-term-execution-plan.plan.md` | Implementer companion (W1–W4+S4, checklists, slice boilerplate) |

## Planned / Working

| Path | Role |
|---|---|
| `docs/plans/docs-inventory-master.md` | Lifecycle inventory and classification table |
| `docs/plans/docs-authority-map.md` | Authority and precedence map for docs |
| `docs/plans/docs-archive-index.md` | Archive index and replacement mapping |
| `docs/plans/notebook-standards.md` | Notebook standards and ownership |
| `docs/plans/control-plane-product-alignment-plan.md` | Control plane vs adapter vs customer bridge narrative |
| `docs/plans/adapter-packages-extraction-handoff.md` | Adapter packages extraction checklist (separate repos) |

## Archived / Historical

| Path | Replacement |
|---|---|
| `docs/archive/plans/backlog-reconciliation-v2-execution-board.md` | `docs/plans/tenant-tool-execution-architecture.md` |
| `docs/archive/plans/backlog-reconciliation-v3-execution-board.md` | `docs/plans/tenant-tool-execution-architecture.md` |
| `docs/archive/plans/backlog-reconciliation-v3-execution-plan.md` | `docs/plans/tenant-tool-execution-architecture.md` |
| `docs/archive/plans/backlog-reconciliation-v4-execution-board.md` | `docs/plans/tenant-tool-execution-architecture.md` |
| `docs/archive/plans/p2-expansion-roadmap.md` | `docs/plans/tenant-tool-execution-architecture.md` |
| `docs/archive/operations/local-ui-readiness-smoke.md` | `docs/operations/release-candidate-signoff-checklist.md` |
| `docs/archive/results/audit_alignment_results.md` | `.local/workflow-artifacts/alignment/alignment-audit.md` |
| `docs/archive/results/audit_alignment_action_plan.md` | `.local/workflow-artifacts/alignment/alignment-todos.md` |
| `docs/archive/plans/api-platform.md` | `docs/plans/tenant-tool-execution-architecture.md`, `docs/architecture/ARCHITECTURE.md` |
| `docs/archive/plans/platform-extensions.md` | `docs/plans/tenant-tool-execution-architecture.md`, `docs/plans/option-c-contract-freeze.md`, `docs/plans/option-c-worker-isolation-contract.md`, `docs/plans/option-c-performance-gates.md` |
| `docs/archive/plans/archive-agents-research.md` | N/A — use `.cursor/agents`, `.cursor/skills`, `.agents/skills` for current automation assets |
| `docs/archive/plans/docs-inventory.md` | `docs/plans/docs-inventory-master.md` |
| `docs/archive/plans/notebooks-inventory.md` | `notebooks/README.md`, `docs/plans/notebook-standards.md` |
| `docs/archive/plans/docs-governance-baseline-map.md` | `docs/plans/docs-authority-map.md`, `docs/plans/docs-archive-index.md` |
| `docs/archive/plans/northbound-v1-gateway.md` | `docs/api/customer-api-integration-guide.md` (§4.0), `docs/plans/tenant-tool-execution-architecture.md`, `src/api/routers/openai_gateway.py` |
| `docs/archive/plans/enterprise-audit-remediation-plan.md` | `docs/strategy/traceability-matrix.md`, `docs/plans/tenant-tool-execution-architecture.md`, `.github/workflows/architecture-fitness.yml` |
| `docs/archive/plans/documentation-cleanup-master-plan.md` | `docs/plans/docs-inventory-master.md`, `docs/plans/docs-authority-map.md`, `docs/governance/drift-prevention.md` |
| `docs/archive/plans/docs-and-notebooks-cleanup-plan.md` | `docs/plans/notebook-standards.md`, `notebooks/README.md`, `docs/plans/docs-inventory-master.md` |
| `docs/archive/plans/post-monolith-execution-roadmap.md` | `docs/strategy/next-directions.md`, `docs/plans/short-long-term-execution-plan.md`, `docs/strategy/traceability-matrix.md`, `docs/plans/tenant-tool-execution-architecture.md` |
| `docs/archive/plans/adapter-ecosystem-gateway-hygiene-plan.md` | `docs/strategy/adapter-strategy.md`, `docs/strategy/next-directions.md`, `docs/plans/adapter-packages-extraction-handoff.md`, `docs/plans/short-long-term-execution-plan.md` |
| `docs/archive/plans/adapter-ecosystem-gateway-hygiene-todos.md` | Same as hygiene plan (checkbox snapshot) |
| `docs/archive/plans/control-plane-product-alignment-baseline-slice-closed.md` | `docs/plans/control-plane-product-alignment-plan.md` (ongoing L1–L4) |

## Notes

- `docs/archive/*` contains non-authoritative historical documents with replacement pointers.
- `.local/*` artifacts are execution evidence snapshots and not long-lived canonical docs.
