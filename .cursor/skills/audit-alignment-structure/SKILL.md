---
name: audit-alignment-structure
description: Audits repository/module/test structure against roadmap and architecture declarations.
---

# Audit Alignment - Structure

## Goal

Find structural drift between declared module boundaries and implemented layout.

## Inputs

- `docs/architecture_mvp.md`
- `docs/roadmap/*`
- `.cursor/research-for-refactor/13-project-structure-blueprint.md`
- `src/*`
- `tests/modules/*`
- CI workflow files in `.github/workflows/*`

## Checks

1. Module directories declared vs present.
2. Test layout conventions declared vs present.
3. CI test paths refer to existing files.
4. Docs reference current folder/file paths.

## Output

Produce schema-constrained findings only, using categories:

- `stale_doc_reference`
- `ci_path_drift`
- `module_traceability_gap`
- `test_coverage_mapping_gap`
