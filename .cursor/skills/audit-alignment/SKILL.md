---
name: audit-alignment
description: Compatibility shim that delegates to the canonical maintainer audit skill.
disable-model-invocation: true
---

# Audit Alignment (Compatibility Shim)

## Canonical Source

Use `.agents/skills/audit-alignment/SKILL.md` as the single source of truth for behavior, constraints, and outputs.

## Delegation Contract

When invoked through this path:

1. Read `.agents/skills/audit-alignment/SKILL.md`.
2. Execute that canonical instruction set exactly.
3. Preserve advisory-only behavior and required outputs:
   - `.local/alignment-audit.md`
   - `.local/alignment-todos.md`

## Note

This shim exists for backward compatibility with older references under `.cursor/skills/`.
