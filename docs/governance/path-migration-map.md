<!--
File: path-migration-map.md
Path: docs/governance/path-migration-map.md
Role: Authoritative old → new path map for enterprise docs/local IA migration.
Used By:
 - scripts/dev/migrate_local_workspace_layout.py
Depends On:
 - docs/operations/local-workspace-layout.md
Notes:
 - Run the migration script after pulling changes; it moves files inside gitignored `.local/`.
-->

# Path migration map

## Strategy (`architecture-goals` → `docs/strategy`)

| From | To |
|------|-----|
| `architecture-goals/*.md` (full content) | `docs/strategy/<kebab-name>.md` |
| `architecture-goals/*.md` (after migration) | **Retired** from repo; optional local stubs via `scripts/dev/write_architecture_goals_redirect_stubs.py` |

## Durable docs (from `.local/index-and-planning/` → `docs/`)

| From | To |
|------|-----|
| `architecture.md` | `docs/architecture/workspace-architecture.md` |
| `agent-workflow-procedures.md` | `docs/operations/agent-workflow-procedures.md` |
| `workflow-complete.md` | `docs/operations/workflow-complete.md` |
| `logging-and-errors.md` | `docs/operations/logging-and-errors.md` |
| `archive-agents.md` | `docs/archive/plans/archive-agents-research.md` |

## `.local` layout (flat / legacy → nested)

| From | To |
|------|-----|
| `index-and-planning/plan.md` | `index-and-planning/current/plan.md` |
| `index-and-planning/work-tracker.md` | `index-and-planning/current/work-tracker.md` |
| `index-and-planning/test-plan.md` | `index-and-planning/current/test-plan.md` |
| `index-and-planning/test-index.md` | `index-and-planning/current/test-index.md` |
| `index-and-planning/coverage-index.md` | `index-and-planning/current/coverage-index.md` |
| `index-and-planning/updates-log.md` | `index-and-planning/history/updates-log.md` |
| `index-and-planning/agent-governance-audit.md` | `index-and-planning/audits/agent-governance-audit.md` |
| `index-and-planning/agent-governance-todos.md` | `index-and-planning/audits/agent-governance-todos.md` |
| `agents-control-center/implementation-control-center.html` | `agents-control-center/dashboards/implementation-control-center.html` |
| `agents-control-center/module-audit.html` | `agents-control-center/audits/module-audit.html` |
| `workflow-artifacts/review.md` | `workflow-artifacts/pr/review.md` |
| `workflow-artifacts/prep.md` | `workflow-artifacts/pr/prep.md` |
| `workflow-artifacts/merge.md` | `workflow-artifacts/pr/merge.md` |
| `workflow-artifacts/alignment-audit.md` | `workflow-artifacts/alignment/alignment-audit.md` |
| `workflow-artifacts/alignment-todos.md` | `workflow-artifacts/alignment/alignment-todos.md` |
| `generated-data/coverage.json` | `generated-data/coverage/coverage.json` |
| `.local/rc-signoff.md` | `workflow-artifacts/release/rc-signoff.md` |
| `.local/rc-signoff.json` | `workflow-artifacts/release/rc-signoff.json` |
| `.local/db-validate-meta.json` | `generated-data/validation/db-validate-meta.json` |
| `.local/ui-e2e-smoke.json` | `generated-data/ui/ui-e2e-smoke.json` |
| `.local/ui-smoke-runtime-snapshots.json` | `generated-data/ui/ui-smoke-runtime-snapshots.json` |
| `.local/byoc-governance-metrics.json` | `generated-data/governance/byoc-governance-metrics.json` |

## Architecture doc redirect

| From | To |
|------|-----|
| `docs/architecture_mvp.md` | `docs/architecture/mvp.md` (stub remains at old path) |
