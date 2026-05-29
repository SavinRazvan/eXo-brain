<!--
File: rollout-phases.md
Path: docs/governance/rollout-phases.md
Role: Reversible rollout sequence for enterprise docs + local workspace IA.
Used By:
 - Planning multi-slice execution
Depends On:
 - docs/governance/path-migration-map.md
Notes:
 - Phases A–D mirror the approved enterprise plan; baseline IA rollout is complete.
 - Ongoing hygiene: drift-prevention.md + documentation-maintenance-checklist.md.
 - Last reviewed: 2026-05-29
-->

# Rollout phases (baseline complete)

**Status:** Historical record of the docs/local IA rollout. **Ongoing** maintenance is not tracked here — use [drift-prevention.md](drift-prevention.md) and [documentation-maintenance-checklist.md](../operations/documentation-maintenance-checklist.md).

## Completed baseline (reference)

1. **Docs taxonomy** — `docs/strategy/`, `docs/architecture/`, `docs/governance/`, later `docs/roadmap/`, `docs/api/`, `docs/modules/`, `docs/decisions/`, `docs/handoffs/`.
2. **Strategy migration** — root `architecture-goals/` retired; canonical under `docs/strategy/` only.
3. **Durable local prose** — procedures/workflows/logging under `docs/operations/`.
4. **Nested `.local` contract** — [path-migration-map.md](path-migration-map.md); `scripts/pr/local_workflow_paths.py`; `scripts/dev/migrate_local_workspace_layout.py`.
5. **Dashboard contract** — `docs/templates/local-workspace/pages.json` + template HTML.
6. **Reference cleanup** — README, AGENTS, Cursor rules/skills, tests, CI aligned.

## Rollback (if reverting an IA slice)

- Revert the git slice; run **`python scripts/dev/migrate_local_workspace_layout.py --dry-run`** before mutating `.local/` on downgrade.
