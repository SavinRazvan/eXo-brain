<!--
File: folder-charter.md
Path: docs/governance/folder-charter.md
Role: Charter for durable documentation (`docs/`) vs local operating workspace (`.local/`).
Used By:
 - docs/governance/README.md
 - Onboarding, maintainers, agent orientation
Depends On:
 - docs/plans/docs-authority-map.md
 - docs/operations/local-workspace-layout.md
Notes:
 - `.local/` is gitignored; this file is the versioned contract for what belongs where.
 - Last reviewed: 2026-05-29
-->

# Folder charter: `docs/` vs `.local/`

## `docs/` (single durable documentation home)

| Subtree | Purpose |
|---------|---------|
| `docs/strategy/` | Product direction, monetization, entitlements, traceability ([README](../strategy/README.md)) |
| `docs/architecture/` | Enduring architecture doctrine, governed turn ordering ([README](../architecture/README.md)) |
| `docs/modules/` | Module-level maintainer contracts ([README](../modules/README.md)) |
| `docs/api/` | Customer integration (control plane HTTP; optional `/v1` bridge) ([README](../api/README.md)) |
| `docs/operations/` | Runbooks, maintainer workflows, RC signoff, `.local/` layout map |
| `docs/plans/` | Active plans, inventories, authority map, archives index |
| `docs/roadmap/` | Alignment audit schema/templates; module hardening program ([README](../roadmap/README.md)) |
| `docs/decisions/` | ADR-style decisions ([README](../decisions/README.md)) |
| `docs/handoffs/` | Completed mission status + pointers ([README](../handoffs/README.md)) |
| `docs/governance/` | Authority, drift prevention, charters (this folder) |
| `docs/archive/` | Historical material only |
| `docs/releases/` | Release note templates (when used) |
| `docs/templates/local-workspace/` | Versioned stubs to copy into `.local/` (e.g. `pages.json`) |

**Repo root (not under `docs/`):**

| Path | Purpose |
|------|---------|
| `notebooks/` | Tutorials, checks, edge proofs ([README](../../notebooks/README.md)) |
| `packages/eXo_adapters/` | In-tree mirror of adapter packages (PyPI **0.1.1**) |
| `src/` | Control-plane implementation |

## `.local/` (local operating workspace — not canonical policy storage)

| Subtree | Purpose |
|---------|---------|
| `index-and-planning/current/` | Live trackers: `plan.md`, `work-tracker.md`, `test-plan.md`, `test-index.md`, `coverage-index.md` |
| `index-and-planning/history/` | Chronological logs (e.g. `updates-log.md`) |
| `index-and-planning/audits/` | Local governance audit snapshots |
| `agents-control-center/dashboards/` | HTML shells: landing + manifest-driven dashboards |
| `agents-control-center/audits/` | Deep audit HTML exports (e.g. module map) |
| `agents-control-center/config/` | `pages.json` and local UI config |
| `agents-control-center/data/` | Generated summaries for dashboards |
| `workflow-artifacts/pr/` | `review.md`, `prep.md`, `merge.md` (PR phase headers — not git commit trailers) |
| `workflow-artifacts/alignment/` | Focused alignment pass: `alignment-audit.md`, `alignment-todos.md` |
| `workflow-artifacts/enterprise-architecture-audit/` | Full enterprise audit report + `enterprise-audit-actions.md` |
| `workflow-artifacts/release/` | RC signoff (`rc-signoff.md`, etc.) |
| `generated-data/coverage/` | `coverage.json` and similar machine output |
| `generated-data/validation/`, `ui/`, `governance/` | Other generated snapshots |

Full layout: [local-workspace-layout.md](../operations/local-workspace-layout.md). Paths in [path-migration-map.md](path-migration-map.md) are relative to `.local/` unless noted.

## `architecture-goals/` (retired)

- Removed from the repo; canonical strategy content lives in **`docs/strategy/`** only.
- Optional: `scripts/dev/write_architecture_goals_redirect_stubs.py` for external links to old paths.

## What does not belong in `docs/`

- PR phase artifacts (`review.md` / `prep.md` / `merge.md`) — **`.local/workflow-artifacts/pr/`** only.
- Live slice trackers — **`.local/index-and-planning/current/`** (summarize outcomes in `updates-log.md`; durable doctrine stays in `docs/`).
- Generated coverage/CI JSON — **`.local/generated-data/`** (protected: `.exo_data/`, `.coverage` per [local-artifact-protection.mdc](../../.cursor/rules/local-artifact-protection.mdc)).
