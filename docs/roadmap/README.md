<!--
File: README.md
Path: docs/roadmap/README.md
Role: Index for alignment audit contracts and module-hardening program docs.
Used By:
 - docs/README.md
 - docs/plans/docs-inventory-master.md
 - .cursor/rules/advisory-audit-alignment-enforcement.mdc
Depends On:
 - docs/roadmap/alignment-audit-schema.md
 - docs/roadmap/enterprise-module-hardening-integration-plan.md
Notes:
 - Alignment outputs live under .local/workflow-artifacts/alignment/ (gitignored).
-->

# Roadmap documentation

**Status:** active  
**Owner:** Savin I. Razvan  
**Last reviewed:** 2026-05-29

Two purposes: **(A)** advisory alignment audits before architecture-impacting merges, and **(B)** a phased **module hardening** program for `src/*` quality without breaking provider-neutral boundaries.

## A) Alignment audits (advisory)

| Document | Role |
|---|---|
| [alignment-audit-schema.md](alignment-audit-schema.md) | Required finding fields, severity, categories, precedence |
| [alignment-audit-report-template.md](alignment-audit-report-template.md) | Paste into `.local/workflow-artifacts/alignment/alignment-audit.md` |
| [alignment-todos-template.md](alignment-todos-template.md) | Paste into `.local/workflow-artifacts/alignment/alignment-todos.md` |

**Agent:** `enterprise-auditor` + [.cursor/skills/enterprise-architecture-audit/SKILL.md](../../.cursor/skills/enterprise-architecture-audit/SKILL.md) (focused alignment pass for PR scope).

**Rule:** [.cursor/rules/advisory-audit-alignment-enforcement.mdc](../../.cursor/rules/advisory-audit-alignment-enforcement.mdc) — run before `/prepare-pr` when scope touches module boundaries, workflow/policy, test layout, or doc source-of-truth.

**P0 findings** block merge prep until fixed or `accepted_divergence` with rationale.

## B) Module hardening program

| Document | Role |
|---|---|
| [enterprise-module-hardening-integration-plan.md](enterprise-module-hardening-integration-plan.md) | Phased order, success criteria, tracking table |
| [module-hardening-slice-checklist.md](module-hardening-slice-checklist.md) | Per-PR checklist (validation, logs, errors, tests, PR artifacts) |

The tracking table describes **program slices**, not overall product readiness. Much of the platform baseline (API, orchestration, adapters on PyPI) may already ship while a slice row remains `planned`.

## Merge gates (canonical)

Default PR prep order: `scripts/pr/prepare.py` (`GATES`) — `check_testing_artifacts.py`, `pytest -q`, `validate_layers.py`, `scan_forbidden_imports.py`.

When changing governance, workflows, or tracked policy docs, also run `python scripts/architecture/check_governance_consistency.py` (see `AGENTS.md`).

## Related docs

- [workspace-architecture.md](../architecture/workspace-architecture.md) — modular monolith boundaries
- [docs/modules/README.md](../modules/README.md) — P0 module maintainer contracts
- [traceability-matrix.md](../strategy/traceability-matrix.md) — strategy ↔ code ↔ tests
- [release-candidate-signoff-checklist.md](../operations/release-candidate-signoff-checklist.md) — references alignment schema
