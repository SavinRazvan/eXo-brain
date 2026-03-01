---
name: audit-alignment
description: Runs an advisory-only cross-source alignment audit and outputs deterministic findings and reconciliation tasks.
---

# Audit Alignment (Advisory-Only)

## Goal

Detect drift between roadmap, research, implementation, and governance artifacts without changing files.

## Required Sources

- `docs/roadmap/*`
- `.cursor/research-for-refactor/*`
- `.cursor/PORTABLE_PACK.md`
- `src/*`
- `tests/modules/*`
- `AGENTS.md`
- `.agents/skills/*`
- `.cursor/rules/*`
- `.cursor/skills/*`
- `.local/*` (if present)

## Mandatory Constraints

1. Advisory-only mode: findings + recommendations only.
2. Use the shared schema in `docs/roadmap/alignment-audit-schema.md`.
3. Every finding must include evidence and recommended remediation.
4. Respect precedence from the schema doc when sources conflict.

## Execution Steps

1. Run structure audit (`audit-alignment-structure`).
2. Run policy/workflow audit (`audit-alignment-policy`).
3. Run module traceability audit (`audit-alignment-traceability`).
4. Merge findings, de-duplicate IDs, classify P0/P1/P2.
5. Emit:
   - `.local/alignment-audit.md` (report format from template)
   - `.local/alignment-todos.md` (prioritized reconciliation actions)

## Output Contract

Each finding must include:

- `id`
- `severity`
- `category`
- `source_path`
- `target_path`
- `evidence`
- `recommendation`
- `status`
