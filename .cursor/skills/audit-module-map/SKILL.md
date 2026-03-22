---
name: audit-module-map
description: Builds a deep per-module workflow map with importance, goals, and visual architecture output.
---

# Audit Module Map (Advisory-Only)

## Goal

Produce a module-by-module audit that explains workflow, behavior, importance, and intended goal, with a visual architecture map and detailed results.

## When to Use

- User asks for a deep codebase/module audit.
- Team needs a current module map before architecture reconciliation.
- Documentation drift is suspected across module boundaries and ownership.

## Required Sources

- `README.md`
- `AGENTS.md`
- `architecture-goals/*`
- `docs/plans/*` (current-state sources)
- `src/*` (all module roots)
- `tests/modules/*`
- `.cursor/rules/*` and `.cursor/skills/*`
- `.agents/skills/*` (maintainer workflow context)

## Mandatory Constraints

1. Advisory-only: do not auto-remediate findings during this audit.
2. Use evidence-backed statements only; include concrete file paths for each claim.
3. Distinguish canonical current-state docs from archival/historical docs.
4. Mark uncertain ownership as `TBD` and call out required follow-up.

## Execution Steps

1. Inventory module roots under `src/` and map corresponding test ownership under `tests/modules/`.
2. For each module, document:
   - goal
   - workflow/how it works (entrypoints, key contracts, control flow)
   - importance (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`) with rationale
   - key dependencies and key dependents
3. Build an architecture-layer graphic showing module placement and directional data/control flow.
4. Identify drift/gaps in:
   - module-to-test mapping
   - module documentation coverage
   - rules/skill guidance needed for repeatable audits
5. Emit:
   - `.local/module-map.md` (detailed module catalog)
   - `.local/agents-control-center/module-audit.html` (visual report with architecture graphic and per-module cards)
   - Optional reconciliation findings appended into `.local/alignment-audit.md` and `.local/alignment-todos.md`

## Output Contract

For each module entry, include:

- `module_name`
- `source_paths`
- `test_paths`
- `importance`
- `goal`
- `workflow`
- `key_contracts`
- `dependencies`
- `dependents`
- `evidence`
- `gaps_or_risks`

## Exit Criteria

- Every production module has an explicit ownership/mapping entry (or `TBD` with rationale).
- The architecture graphic and module deep-dive results are generated and readable.
- Any accuracy-improving updates needed for rules/skills/agents are explicitly listed with evidence.
