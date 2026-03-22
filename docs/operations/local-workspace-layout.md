<!--
File: local-workspace-layout.md
Path: docs/operations/local-workspace-layout.md
Role: Describes the intended layout under `.local/` for planning markdown, HTML dashboards, generated metrics, and PR workflow artifacts.
Used By:
 - Maintainers and agents (see AGENTS.md, .cursor/agents, .cursor/skills)
Depends On:
 - scripts/pr/prepare.py (GATES use check_testing_artifacts against planning dir)
 - scripts/pr/local_workflow_paths.py (PR artifact paths)
 - scripts/dev/generate_coverage_index.py
Notes:
 - `.local/` is gitignored; this doc is the durable map when clones are fresh.
-->

# Local workspace layout (`.local/`)

Ephemeral operating state lives under **`.local/`** (not committed). Use this structure:

| Path | Purpose |
|------|--------|
| **`index-and-planning/`** | Planning and execution trackers: `plan.md`, `work-tracker.md`, `updates-log.md`, `workflow-complete.md`, `test-plan.md`, `test-index.md`, `coverage-index.md`, governance notes, etc. |
| **`agents-control-center/`** | Local HTML shells: `implementation-control-center.html` (tabs over markdown in `index-and-planning/`), `module-audit.html` (deep audit export when regenerated). Open HTML via local file or static server. |
| **`generated-data/`** | Machine outputs consumed by scripts, e.g. `coverage.json` from `coverage json`. |
| **`workflow-artifacts/`** | PR phase outputs from `scripts/pr/*`: `review.md`, `prep.md`, `merge.md`, and (when required) `alignment-audit.md`, `alignment-todos.md`. |
| **`.local/` root (other)** | RC signoff, smoke metrics, and other JSON snapshots may remain at `.local/` root until further cleanup. |

## Script alignment

- **`scripts/pr/check_testing_artifacts.py`** — expects `test-plan.md` and `test-index.md` under **`--planning-dir`** (default: `.local/index-and-planning`). **`--control-center-dir`** is a deprecated alias.
- **`scripts/dev/generate_coverage_index.py`** — reads **`--coverage-json`** (default `.local/generated-data/coverage.json`), writes **`--output`** (default `.local/index-and-planning/coverage-index.md`).
- **`make coverage-index`** — runs pytest with coverage, writes JSON to `generated-data`, then regenerates the markdown index.
- **`scripts/pr/review.py`**, **`prepare.py`**, **`merge.py`** — read/write markdown under **`workflow-artifacts/`** (see **`scripts/pr/local_workflow_paths.py`**).

## Migrating from `control-center/`

Older clones used **`.local/control-center/`** and **`.local/implementation-control-center.html`**. Those paths are retired: move markdown into **`index-and-planning/`**, HTML into **`agents-control-center/`**, and refresh **`implementation-control-center.html`** `PAGES` paths to **`../index-and-planning/...`**.

## Migrating PR artifacts from `.local/` root

If **`review.md`**, **`prep.md`**, **`merge.md`**, or alignment files still live at **`.local/*.md`**, move them into **`.local/workflow-artifacts/`** so the PR scripts find them.
