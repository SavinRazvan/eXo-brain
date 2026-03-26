<!--
File: drift-prevention.md
Path: docs/governance/drift-prevention.md
Role: Lightweight process to keep docs, `.local` layout docs, and script-first workflow aligned.
Used By:
 - Maintainers after governance or workflow edits
Depends On:
 - scripts/pr/prepare.py
 - scripts/architecture/check_governance_consistency.py
 - docs/plans/docs-authority-map.md
 - docs/plans/docs-inventory-master.md
Notes:
 - Run governance consistency when changing rules, skills headers, or merge.py string expectations.
-->

# Drift prevention (lightweight)

## After changing workflow gates or artifact paths

1. Update **`scripts/pr/prepare.py`** (`GATES`) if commands change.
2. Update **`.cursor/rules/pr-workflow-enforcement.mdc`** one-liners (no long duplication).
3. Update **`docs/operations/workflow-complete.md`** and **`docs/operations/agent-workflow-procedures.md`** if user-facing checklist text references paths or commands.
4. Update **`README.md`** / **`AGENTS.md`** if onboarding paths change.
5. Run **`python scripts/architecture/check_governance_consistency.py`** and **`python -m pytest -q`**.

## After changing documentation lifecycle

1. Update **`docs/plans/docs-inventory-master.md`** row(s).
2. If precedence shifts, update **`docs/plans/docs-authority-map.md`**.

## After changing `.local` layout

1. Update **`docs/operations/local-workspace-layout.md`** and **`docs/governance/path-migration-map.md`**.
2. Update **`scripts/pr/local_workflow_paths.py`** (and dependents) for workflow artifacts.
3. Refresh **`docs/templates/local-workspace/pages.json`** if dashboard tabs change.

## Quarterly

- Skim **`docs/strategy/next-directions.md`** vs **`docs/plans/tenant-tool-execution-architecture.md`** for obvious stale claims.
- Skim **`docs/strategy/governed-execution-positioning.md`**, **`docs/plans/control-plane-product-alignment-plan.md`**, and **`docs/strategy/traceability-matrix.md`** against **`docs/api/customer-api-integration-guide.md`** and **`docs/architecture/ARCHITECTURE.md`** so **control plane** / **customer bridge** / **provider runtime adapter** language does not drift.
