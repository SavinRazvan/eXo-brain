<!--
File: rollout-phases.md
Path: docs/governance/rollout-phases.md
Role: Reversible rollout sequence for enterprise docs + local workspace IA.
Used By:
 - Planning multi-slice execution
Depends On:
 - docs/governance/path-migration-map.md
Notes:
 - Phases A–D mirror the approved enterprise plan; this file tracks completion state only.
-->

# Rollout phases (completed in this slice)

1. **Docs taxonomy** — `docs/strategy/`, `docs/architecture/` expansion, `docs/governance/` charters.
2. **Strategy migration** — `architecture-goals/` → redirect stubs; canonical under `docs/strategy/`.
3. **Durable local prose** — procedures/workflows/logging/archive research under `docs/`.
4. **Nested `.local` contract** — paths documented; `scripts/pr/local_workflow_paths.py` + scripts updated; migration helper added.
5. **Dashboard contract** — versioned `pages.json` + template HTML under `docs/templates/local-workspace/`.
6. **Reference cleanup** — README, AGENTS, Cursor surfaces, tests, CI aligned.

## Rollback

- Revert the git slice; re-run **`python scripts/dev/migrate_local_workspace_layout.py --dry-run`** before mutating `.local/` on downgrade.
