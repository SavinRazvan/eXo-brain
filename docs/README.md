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
2. `docs/strategy/goal.md` + `docs/strategy/next-directions.md` (direction)
3. `docs/architecture/beginner-workflow.md` (plain-language walkthrough)
4. `docs/architecture/mvp.md` + `docs/architecture/workspace-architecture.md` (shape)
5. `docs/plans/tenant-tool-execution-architecture.md` (implementation status)
6. `docs/operations/workflow-complete.md` (maintainer path)
7. `docs/operations/local-workspace-layout.md` (gitignored `.local/` contract)

## Strategy (`docs/strategy/`)

- `docs/strategy/README.md` — index and reading order
- `docs/strategy/governed-execution-positioning.md` — product boundary, ICP, and monetization direction
- `docs/strategy/next-directions.md` — prioritized tiers
- `docs/strategy/entitlement-matrix.md`, `docs/strategy/traceability-matrix.md`, etc.

> `architecture-goals/` at repo root holds **redirect stubs** only; edit `docs/strategy/*`.

## Architecture (`docs/architecture/`)

- `docs/architecture/README.md`
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

## Planning and cleanup governance

- `docs/plans/documentation-cleanup-master-plan.md`
- `docs/plans/docs-inventory-master.md`
- `docs/plans/docs-authority-map.md`
- `docs/plans/docs-archive-index.md`
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
