<!--
File: local-workspace-layout.md
Path: docs/operations/local-workspace-layout.md
Role: Versioned map of the gitignored `.local/` operating workspace (nested layout).
Used By:
 - AGENTS.md, maintainer onboarding, migrate script
Depends On:
 - scripts/pr/local_workflow_paths.py
 - scripts/dev/migrate_local_workspace_layout.py
 - docs/governance/path-migration-map.md
Notes:
 - Run `python scripts/dev/migrate_local_workspace_layout.py` after upgrades if your tree is still flat.
-->

# Local workspace layout (`.local/`)

The `.local/` directory is **gitignored**. This document is the **versioned contract** for how it should be organized.

## Top-level buckets

| Path | Purpose |
|------|---------|
| **`index-and-planning/current/`** | Live trackers: `plan.md`, `work-tracker.md`, `test-plan.md`, `test-index.md`, `coverage-index.md`, `architecture.md` (stub → `docs/architecture/workspace-architecture.md`) |
| **`index-and-planning/history/`** | Chronological logs (e.g. `updates-log.md`, optional legacy snapshots) |
| **`index-and-planning/audits/`** | Local governance audit markdown (`agent-governance-audit.md`, `agent-governance-todos.md`) |
| **`agents-control-center/dashboards/`** | `implementation-control-center.html` (manifest-driven) |
| **`agents-control-center/audits/`** | `module-audit.html` and similar exports |
| **`agents-control-center/config/`** | `pages.json` — tab labels + relative paths to markdown |
| **`agents-control-center/data/`** | Optional `summary.json` for UI summaries |
| **`workflow-artifacts/pr/`** | `review.md`, `prep.md`, `merge.md` from `scripts/pr/*` |
| **`workflow-artifacts/alignment/`** | `alignment-audit.md`, `alignment-todos.md` |
| **`workflow-artifacts/release/`** | RC signoff and release-local artifacts |
| **`generated-data/coverage/`** | `coverage.json` from `coverage json` |
| **`generated-data/validation/`**, **`ui/`**, **`governance/`** | Other generated JSON snapshots |

## Durable documentation (not in `.local`)

Canonical workflow and doctrine live under **`docs/`**:

- `docs/operations/workflow-complete.md`
- `docs/operations/agent-workflow-procedures.md`
- `docs/operations/logging-and-errors.md`
- `docs/plans/archive-agents-research.md`
- `docs/architecture/workspace-architecture.md`
- `docs/strategy/*` (strategy package; `architecture-goals/` holds redirect stubs only)

## Script alignment

| Script | Behavior |
|--------|----------|
| **`scripts/pr/check_testing_artifacts.py`** | Default `--planning-dir`: `.local/index-and-planning/current` |
| **`scripts/dev/generate_coverage_index.py`** | Reads `.local/generated-data/coverage/coverage.json`, writes `.local/index-and-planning/current/coverage-index.md` |
| **`make coverage-index`** | Same paths as above |
| **`scripts/pr/review.py`**, **`prepare.py`**, **`merge.py`** | Artifacts under **`workflow-artifacts/pr/`** and **`alignment/`** (see **`local_workflow_paths.py`**) |

## Templates (versioned in git)

Copy or sync from **`docs/templates/local-workspace/`** into `.local/agents-control-center/`:

- `pages.json` → `config/pages.json`
- `implementation-control-center.html` → `dashboards/implementation-control-center.html`

The **`migrate_local_workspace_layout.py`** helper copies these when missing.

## Migrating from flat layout

1. `python scripts/dev/migrate_local_workspace_layout.py --dry-run`
2. `python scripts/dev/migrate_local_workspace_layout.py`

See **`docs/governance/path-migration-map.md`** for the full old → new map.
