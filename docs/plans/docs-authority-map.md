<!--
File: docs-authority-map.md
Path: docs/plans/docs-authority-map.md
Role: Defines documentation precedence and conflict resolution for this repository.
Used By:
 - docs/README.md
 - docs/plans/README.md
Depends On:
 - .cursor/rules/pr-workflow-enforcement.mdc
 - .agents/skills/PR_WORKFLOW.md
 - docs/plans/docs-inventory-master.md
Notes:
 - Use this map when two docs overlap or conflict.
-->

# Documentation Authority Map

## Precedence Order

1. **Repository rules and governance contracts**
   - `.cursor/rules/*.mdc`
   - `AGENTS.md`
2. **Maintainer workflow source**
   - `.agents/skills/PR_WORKFLOW.md`
3. **Canonical active docs**
   - `README.md`
   - `docs/architecture_mvp.md`
   - `docs/runtime_contracts.md`
   - `docs/plans/tenant-tool-execution-architecture.md`
   - `docs/operations/release-candidate-signoff-checklist.md`
4. **Planning docs**
   - `docs/plans/*` files marked active/planned
5. **Historical docs**
   - `docs/*` files marked archived/historical
   - `.cursor/research-for-refactor/*` (supporting unless explicitly promoted)

## Conflict Resolution Rules

- If workflow wording differs, `.cursor/rules/pr-workflow-enforcement.mdc` wins.
- If PR step details differ, `.agents/skills/PR_WORKFLOW.md` wins over `README.md`.
- If operational gate wording differs, `docs/operations/release-candidate-signoff-checklist.md` wins.
- If historical plan guidance conflicts with current implementation, `docs/plans/tenant-tool-execution-architecture.md` wins.

## Required Status Labels

Every major plan/operations doc should include:

- `Status`: `active` / `planned` / `archived`
- `Canonical replacement` (required when `archived`)
- `Owner`
- `Last reviewed`

## Ownership Model

- Primary owner: Maintainer (Savin I. Razvan)
- Update trigger: any PR that changes architecture, workflow, release gates, or API/tenancy behavior.
- Review cadence: quarterly minimum, plus per major slice completion.
