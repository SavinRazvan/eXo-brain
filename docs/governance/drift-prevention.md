<!--
File: drift-prevention.md
Path: docs/governance/drift-prevention.md
Role: Lightweight process to keep docs, `.local` layout docs, and script-first workflow aligned.
Used By:
 - docs/governance/README.md
 - Maintainers after governance or workflow edits
Depends On:
 - scripts/pr/prepare.py
 - scripts/architecture/check_governance_consistency.py
 - docs/plans/docs-authority-map.md
 - docs/plans/docs-inventory-master.md
 - docs/operations/documentation-maintenance-checklist.md
Notes:
 - Run governance consistency when changing rules, skills headers, or merge.py string expectations.
 - Last reviewed: 2026-05-29
-->

# Drift prevention (lightweight)

## Default merge gates (canonical)

Order and commands: **`scripts/pr/prepare.py`** (`GATES`):

1. `python scripts/pr/check_testing_artifacts.py`
2. `python -m pytest -q`
3. `python scripts/architecture/validate_layers.py`
4. `python scripts/architecture/scan_forbidden_imports.py`

Additionally when changing governance, workflows, `.cursor/`, `.agents/`, or tracked policy docs: **`python scripts/architecture/check_governance_consistency.py`**.

Substantive `src/**` work: project standard **`pytest --cov=src --cov-fail-under=95`** before merge (see `AGENTS.md`; CI enforces the same floor via `COV_FAIL_UNDER` in `architecture-fitness.yml`).

## After changing workflow gates or artifact paths

1. Update **`scripts/pr/prepare.py`** (`GATES`) if commands change.
2. Update **`.cursor/rules/pr-workflow-enforcement.mdc`** (short pointers only — no long gate lists in chat).
3. Update **`docs/operations/workflow-complete.md`** and **`docs/operations/agent-workflow-procedures.md`** if checklist text references paths or commands.
4. Update **`README.md`** / **`AGENTS.md`** if onboarding paths change.
5. Run **`python scripts/architecture/check_governance_consistency.py`** and targeted tests.

## After changing documentation lifecycle

1. Update **`docs/plans/docs-inventory-master.md`** row(s).
2. If precedence shifts, update **`docs/plans/docs-authority-map.md`** and [workflow-source-owners.md](workflow-source-owners.md) if ownership moved.

## After API, module, or strategy contract changes

Use **[documentation-maintenance-checklist.md](../operations/documentation-maintenance-checklist.md)** — especially:

- `docs/api/customer-api-integration-guide.md` + `docs/api/README.md` when routes/mounts change
- `docs/modules/*` when `src/` domain contracts change
- `docs/strategy/entitlement-matrix.md`, `traceability-matrix.md`, `adapter-compatibility-matrix.md` when tiers or adapter versions change
- `notebooks/README.md`, `EVALUATOR_GUIDE.md`, `docs/plans/notebook-standards.md` when notebook builders change

## After changing `.local` layout

1. Update **`docs/operations/local-workspace-layout.md`** and **[path-migration-map.md](path-migration-map.md)**.
2. Update **`scripts/pr/local_workflow_paths.py`** (and `review.py` / `prepare.py` / `merge.py` consumers).
3. Refresh **`docs/templates/local-workspace/pages.json`** if dashboard tabs change.
4. Run **`python scripts/dev/migrate_local_workspace_layout.py --dry-run`** before mutating a developer tree.

## After changing **git commit** trailer policy

Follow **`docs/operations/agent-workflow-procedures.md` §3b** (durable + `.local/.../agent-workflow-procedures.md` twin). Includes **`AGENTS.md`**, **`docs/governance/rules-overlap-matrix.md`**, **`docs/governance/workflow-source-owners.md`**, PR scripts, and mirrored `.cursor/` / `.agents/` skills. Run **`check_governance_consistency.py`** when tracked policy paths change.

## Quarterly (or before large releases)

- Skim **`docs/strategy/next-directions.md`** vs **`docs/plans/tenant-tool-execution-architecture.md`**.
- Skim **control plane / customer bridge / adapter** vocabulary across [governed-execution-positioning.md](../strategy/governed-execution-positioning.md), [customer-api-integration-guide.md](../api/customer-api-integration-guide.md), and [ARCHITECTURE.md](../architecture/ARCHITECTURE.md).
- Confirm **`docs/governance/rules-overlap-matrix.md`** still lists all **`.cursor/rules/*.mdc`** files.
