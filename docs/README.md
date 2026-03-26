<!--
File: README.md
Path: docs/README.md
Role: Top-level documentation index for active, planned, and archived content.
Used By:
 - README.md
 - Maintainers and contributors navigating repository documentation
Depends On:
 - docs/plans/docs-inventory-master.md
 - docs/plans/docs-authority-map.md
Notes:
 - Keep this file concise and update links whenever doc status changes.
-->

# Documentation index

## Reading spine (recommended)

1. `README.md` (repository entry)
2. `docs/strategy/goal.md` + `docs/strategy/next-directions.md` (direction) + `docs/plans/short-long-term-execution-plan.md` (**short vs long horizons** and main-UI attach)
3. `docs/architecture/ARCHITECTURE.md` (numbered planes + **control/adapter/data plane** vocabulary map in §2)
4. `docs/architecture/beginner-workflow.md` (plain-language walkthrough)
5. `docs/architecture/mvp.md` + `docs/architecture/workspace-architecture.md` (shape detail)
6. `docs/plans/tenant-tool-execution-architecture.md` (implementation status)
7. `docs/operations/workflow-complete.md` (maintainer path)
8. `docs/operations/local-workspace-layout.md` (gitignored `.local/` contract)

## Strategy (`docs/strategy/`)

- `docs/strategy/README.md` — index and reading order
- `docs/strategy/governed-execution-positioning.md` — product boundary, ICP, and monetization direction
- `docs/strategy/next-directions.md` — prioritized tiers
- `docs/strategy/entitlement-matrix.md`, `docs/strategy/traceability-matrix.md`, etc.

> Root `architecture-goals/` was retired; **edit `docs/strategy/*`** for all strategy content.

## Architecture (`docs/architecture/`)

- `docs/architecture/README.md`
- `docs/architecture/ARCHITECTURE.md` — ten planes; **§2** maps strategy terms (control / governance / adapter / data plane, interface Layer A|B) to code
- `docs/architecture/beginner-workflow.md` — beginner-friendly workflow and analogy guide
- `docs/architecture/mvp.md` — layers and flows
- `docs/architecture/workspace-architecture.md` — workspace doctrine

## Governance (`docs/governance/`)

- `docs/governance/folder-charter.md` — durable vs local boundaries
- `docs/governance/workflow-source-owners.md` — scripts vs docs authority
- `docs/governance/drift-prevention.md` — keep docs aligned with gates
- `docs/governance/path-migration-map.md` — migration reference

## Active canonical docs

- `docs/runtime_contracts.md`
- `docs/mcp_integration.md`
- `docs/plugin_lifecycle.md`
- `docs/workflow_loading.md`
- `docs/plans/tenant-tool-execution-architecture.md`
- `docs/plans/option-c-contract-freeze.md`
- `docs/plans/option-c-worker-isolation-contract.md`
- `docs/plans/option-c-performance-gates.md`
- `docs/operations/release-candidate-signoff-checklist.md`
- `docs/operations/byoc-failure-injection-playbook.md`
- `docs/operations/byoc-artifact-integrity-dashboard.md`
- `docs/operations/documentation-maintenance-checklist.md`

## Operations (workflows)

- `docs/operations/workflow-complete.md`
- `docs/operations/agent-workflow-procedures.md`
- `docs/operations/local-workspace-layout.md`
- `docs/operations/abbreviations-notepad.md` — glossary (**Option C** = control + adapter + data plane); full mapping in `docs/architecture/ARCHITECTURE.md` §2

## Planning and cleanup governance

- `docs/governance/drift-prevention.md` — lightweight anti-drift process (active)
- `docs/plans/docs-inventory-master.md`
- `docs/plans/docs-authority-map.md`
- `docs/plans/docs-archive-index.md`
- `docs/plans/short-long-term-execution-plan.md` — execution horizons (diagrams + tier emphasis)
- `docs/plans/README.md`

## Module docs

- `docs/modules/README.md`

## API docs

- `docs/api/customer-api-integration-guide.md`

## Local workspace templates (copy into `.local/`)

- `docs/templates/local-workspace/pages.json`
- `docs/templates/local-workspace/implementation-control-center.html`
- Run `python scripts/dev/migrate_local_workspace_layout.py` after upgrades

## Historical/archived references

- `docs/archive/operations/local-ui-readiness-smoke.md` (historical)
- `docs/plans/docs-archive-index.md` (full archive mapping)
