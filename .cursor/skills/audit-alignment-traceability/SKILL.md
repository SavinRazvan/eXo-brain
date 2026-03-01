---
name: audit-alignment-traceability
description: Audits per-module traceability from roadmap/research intent to code/tests and governance gates.
---

# Audit Alignment - Traceability

## Goal

Ensure each module has coherent traceability across plan, implementation, tests, and workflow governance.

## Inputs

- `docs/roadmap/*`
- `.cursor/research-for-refactor/*`
- `src/*`
- `tests/modules/*`
- `.github/workflows/*`

## Checks

1. Module appears in roadmap with clear phase/slice ownership.
2. Module has implemented code and corresponding tests.
3. High-impact/state-changing modules reference policy gate expectations.
4. Workflow/CI checks cover required module-level verification.

## Output

Produce schema-constrained findings only, using categories:

- `module_traceability_gap`
- `test_coverage_mapping_gap`
- `naming_or_precedence_drift`
- `workflow_gate_drift`
