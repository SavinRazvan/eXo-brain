# AGENTS.md

## Project Intent

`eXo-brain` is a provider-neutral AI orchestration platform for single-agent and multi-agent workflows.
The core principle is **AI as a commodity**: model providers are pluggable adapters, not orchestration owners.

## Architecture Guardrails

- Keep provider SDK code inside `src/runtime/*adapter*` only.
- Keep core orchestration provider-neutral (`src/core/` must not branch on provider name).
- Route risky or state-changing tool calls through deterministic execution and policy gates.
- Keep strict layer boundaries: `integration -> core -> runtime/tools/policies/persistence/observability`.
- Use typed schemas/contracts for inter-module inputs/outputs.

## Execution Workflow

- Follow sequence: `plan -> interfaces -> implementation -> tests -> evidence -> docs update`.
- Prefer incremental, reversible slices over big-bang rewrites.
- Add rollback/fallback behavior for new runtime features.
- Keep checklist/docs synchronized with implementation status:
  - `.cursor/research-for-refactor/12-bootstrap-checklist.md`
  - `.cursor/research-for-refactor/06-mvp-build-sequence.md`

## Quality and Safety Gates

- Block merge for P0 architecture/safety failures.
- Require tests for happy path, failure path, and replay/retry behavior when relevant.
- Require correlation IDs in runtime paths for auditability.
- Keep architecture fitness checks passing:
  - `scripts/architecture/validate_layers.py`
  - `scripts/architecture/scan_forbidden_imports.py`

## Commit Message Policy

- Commit messages must end with:
  - `Author: <commit author name>`
  - `Made-with: Cursor`
- This format is enforced by:
  - `.cursor/rules/commit-trailer-format.mdc`

## Branching and Release Safety

- Always create a dedicated working branch before coding:
  - `feature/<scope>`, `fix/<scope>`, `chore/<scope>`
- Keep `main` stable and merge-ready; avoid direct implementation commits on `main`.
- Before merge, require:
  - tests and architecture checks passing
  - checklist/research status updates for implemented scope
- Use `git push --force-with-lease` only for intentional history rewrites on your own branch.

## Skills and Agent Extensions

- Primary project skills location: `.cursor/skills/`
- Standards-friendly project skills location: `.agents/skills/`
- Keep skill names stable and use `SKILL.md` per skill directory.
- Maintainer PR workflow is defined in `.agents/skills/PR_WORKFLOW.md` and uses:
  - `.agents/skills/review-pr/SKILL.md`
  - `.agents/skills/prepare-pr/SKILL.md`
  - `.agents/skills/merge-pr/SKILL.md`
