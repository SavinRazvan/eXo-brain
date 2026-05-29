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
   - `AGENTS.md` (includes **§ Commits**: required git trailers + optional `Assisted-by`; canonical detail in **`.cursor/rules/commit-trailer-format.mdc`**)
2. **Maintainer workflow source**
   - `.agents/skills/PR_WORKFLOW.md`
3. **Canonical active docs**
   - `README.md`
   - `docs/strategy/README.md` (strategy package index)
   - Customer self-serve governance spine: `docs/strategy/customer-self-serve-governance-journey.md`, `docs/strategy/foundation-tier-adoption-checklist.md`, `docs/plans/governance-configuration-reference-model.md`, `docs/api/governance-preview-and-testing.md`, `docs/operations/governance-reason-code-catalog.md` (with `docs/api/README.md` + `docs/api/customer-api-integration-guide.md` for wire contracts)
   - `docs/architecture/mvp.md` (see `docs/architecture_mvp.md` stub for legacy links)
   - `docs/architecture/workspace-architecture.md`
   - `docs/runtime_contracts.md`
   - `docs/plans/tenant-tool-execution-architecture.md`
   - `docs/plans/notebook-standards.md`; hands-on index `notebooks/README.md`; evaluator paths `notebooks/EVALUATOR_GUIDE.md`
   - `docs/operations/release-candidate-signoff-checklist.md`
   - `docs/operations/workflow-complete.md`
   - `docs/governance/folder-charter.md`
4. **Planning docs**
   - `docs/plans/*` files marked active/planned
5. **Historical docs**
   - `docs/*` files marked archived/historical
   - `docs/archive/*` (supporting unless explicitly promoted)

## Conflict Resolution Rules

- If workflow wording differs, `.cursor/rules/pr-workflow-enforcement.mdc` wins.
- If PR step details differ, `.agents/skills/PR_WORKFLOW.md` wins over `README.md`.
- If operational gate wording differs, `docs/operations/release-candidate-signoff-checklist.md` wins.
- If historical plan guidance conflicts with current implementation, `docs/plans/tenant-tool-execution-architecture.md` wins.
- Superseded documents must be moved to `docs/archive/*` and indexed in `docs/plans/docs-archive-index.md`.

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
