<!--
File: folder-charter.md
Path: docs/governance/folder-charter.md
Role: Charter for durable documentation (`docs/`) vs local operating workspace (`.local/`).
Used By:
 - Onboarding, maintainers, agent orientation
Depends On:
 - docs/plans/docs-authority-map.md
 - docs/operations/local-workspace-layout.md
Notes:
 - `.local/` is gitignored; this file is the versioned contract for what belongs where.
-->

# Folder charter: `docs/` vs `.local/`

## `docs/` (single durable documentation home)

| Subtree | Purpose |
|---------|---------|
| `docs/strategy/` | Product direction, monetization, entitlements, traceability, execution boards |
| `docs/architecture/` | Enduring architecture doctrine and MVP layer model |
| `docs/modules/` | Module-level technical references |
| `docs/api/` | Consumer integration guidance |
| `docs/operations/` | Runbooks, maintainer workflows, maintenance checklists |
| `docs/plans/` | Active implementation plans, inventories, archives index |
| `docs/governance/` | Authority, drift prevention, charters (this folder) |
| `docs/roadmap/` | Alignment schemas, templates, hardening plans |
| `docs/archive/` | Historical material only |

## `.local/` (local operating workspace — not canonical policy storage)

| Subtree | Purpose |
|---------|---------|
| `index-and-planning/current/` | Live trackers: plan, work-tracker, tests, coverage index |
| `index-and-planning/history/` | Chronological logs (e.g. updates-log) |
| `index-and-planning/audits/` | Local governance audit snapshots |
| `agents-control-center/dashboards/` | HTML shells: `index.html` (landing) + manifest-driven dashboards |
| `agents-control-center/audits/` | Deep audit HTML exports and similar static reports |
| `agents-control-center/config/` | `pages.json` and local UI config |
| `agents-control-center/data/` | Generated summaries for dashboards |
| `workflow-artifacts/pr/` | review / prep / merge markdown |
| `workflow-artifacts/alignment/` | alignment audit + todos |
| `workflow-artifacts/release/` | RC signoff and release artifacts |
| `generated-data/coverage/` | `coverage.json` and similar machine output |
| `generated-data/validation/`, `ui/`, `governance/` | Other generated snapshots |

## `architecture-goals/` (transitional)

- Thin **redirect stubs** only; canonical strategy content lives in **`docs/strategy/`**.
