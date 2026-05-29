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
| `docs/archive/plans/api-platform.md` | `docs/plans/tenant-tool-execution-architecture.md`, `docs/architecture/ARCHITECTURE.md` |
| `docs/archive/plans/platform-extensions.md` | `docs/plans/tenant-tool-execution-architecture.md`, `docs/plans/option-c-contract-freeze.md`, `docs/plans/option-c-worker-isolation-contract.md`, `docs/plans/option-c-performance-gates.md` |
| `docs/archive/plans/archive-agents-research.md` | N/A (see `.cursor/agents`, `.cursor/skills`, `.agents/skills` for current assets) |
| `docs/archive/plans/docs-inventory.md` | `docs/plans/docs-inventory-master.md` |
| `docs/archive/plans/notebooks-inventory.md` | `notebooks/README.md`, `docs/plans/notebook-standards.md` |
| `docs/archive/plans/docs-governance-baseline-map.md` | `docs/plans/docs-authority-map.md`, `docs/plans/docs-archive-index.md` |
| `docs/archive/plans/northbound-v1-gateway.md` | `docs/api/customer-api-integration-guide.md` (§4.0), `docs/plans/tenant-tool-execution-architecture.md`, `src/api/routers/openai_gateway.py` |
| `docs/archive/plans/enterprise-audit-remediation-plan.md` | `docs/strategy/traceability-matrix.md`, `docs/plans/tenant-tool-execution-architecture.md`, `.github/workflows/architecture-fitness.yml` |
| `docs/archive/plans/documentation-cleanup-master-plan.md` | `docs/plans/docs-inventory-master.md`, `docs/plans/docs-authority-map.md`, `docs/governance/drift-prevention.md` |
| `docs/archive/plans/docs-and-notebooks-cleanup-plan.md` | `docs/plans/notebook-standards.md`, `notebooks/README.md`, `docs/plans/docs-inventory-master.md` |
| `docs/archive/plans/post-monolith-execution-roadmap.md` | `docs/strategy/next-directions.md`, `docs/plans/short-long-term-execution-plan.md`, `docs/strategy/traceability-matrix.md`, `docs/plans/tenant-tool-execution-architecture.md` |
| `docs/archive/plans/adapter-ecosystem-gateway-hygiene-plan.md` | `docs/strategy/adapter-strategy.md`, `docs/strategy/next-directions.md`, `docs/plans/adapter-packages-extraction-handoff.md`, `docs/plans/short-long-term-execution-plan.md` |
| `docs/archive/plans/adapter-ecosystem-gateway-hygiene-todos.md` | Same as `adapter-ecosystem-gateway-hygiene-plan.md` (granular checklist snapshot) |
| `docs/archive/plans/control-plane-product-alignment-baseline-slice-closed.md` | `docs/plans/control-plane-product-alignment-plan.md` (§1 executive snapshot + §3–§6 L-phases and ownership) |

## Handoff Archives

| Archived file | Canonical replacement |
|---|---|
| `docs/archive/handoffs/exo_adapters_pypi_handoff-mission.md` | `docs/handoffs/exo_adapters_pypi_handoff.md`, [SavinRazvan/eXo_adapters](https://github.com/SavinRazvan/eXo_adapters), `docs/operations/adapter-installation.md` |

## Operations Archives

| Archived file | Canonical replacement |
|---|---|
| `docs/archive/operations/local-ui-readiness-smoke.md` | `docs/operations/release-candidate-signoff-checklist.md` |

## Result Archives

| Archived file | Canonical replacement |
|---|---|
| `docs/archive/results/audit_alignment_results.md` | `.local/workflow-artifacts/alignment/alignment-audit.md` |
| `docs/archive/results/audit_alignment_action_plan.md` | `.local/workflow-artifacts/alignment/alignment-todos.md` |

## Historical plan snapshots (moved under `docs/archive/plans/`)

Completed or superseded plans in the table above (including **northbound `/v1` design addendum**, **enterprise audit remediation**, **documentation / notebook cleanup waves**, **post-monolith roadmap**, **adapter–gateway hygiene** plans, **api-platform** / **platform-extensions**, inventories, and research snapshots) are **non-authoritative**. When they conflict with current execution status, use:

- `docs/plans/tenant-tool-execution-architecture.md`
- `docs/plans/option-c-contract-freeze.md`
- `docs/plans/option-c-worker-isolation-contract.md`
- `docs/plans/option-c-performance-gates.md`
- `docs/plans/docs-inventory-master.md` (documentation lifecycle)
