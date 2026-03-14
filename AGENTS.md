# AGENTS.md

## Project Intent

`eXo-brain` is a provider-neutral AI orchestration platform for single-agent and multi-agent workflows.
The core principle is **AI as a commodity**: model providers are pluggable adapters, not orchestration owners.
Current delivery posture is API-first Option C (control plane + adapter plane + data plane), with UI/dashboard tracks deferred unless explicitly re-enabled.

## Beginner Orientation

If you are new to the repository, read in this order:
1. `README.md` (architecture map + request/turn workflows)
2. `architecture-goals/NEXT_DIRECTIONS.md` (current priority tiers)
3. `architecture-goals/GOAL.md` (product boundary and non-negotiables)
4. `architecture-goals/ENTITLEMENT_MATRIX.md` (what is Foundation vs Pro vs Enterprise)

Abbreviation notepad:
- `docs/operations/abbreviations-notepad.md`

## Canonical Rules (Always Applied)

- `.cursor/rules/provider-neutral-adapter-wall.mdc` — Architecture and layer boundaries
- `.cursor/rules/execution-workflow-gates.mdc` — Plan → implement → test → docs
- `.cursor/rules/pr-workflow-enforcement.mdc` — PR-first, merge gates, branch safety
- `.cursor/rules/pr-action-attribution.mdc` — GitHub-User in PR artifacts
- `.cursor/rules/commit-trailer-format.mdc` — Commit trailers
- `.cursor/rules/file-docstring-header-relations.mdc` — File header metadata
- `.cursor/rules/local-artifact-protection.mdc` — Protect `.exo_data/`, `.coverage`
- `.cursor/rules/advisory-audit-alignment-enforcement.mdc` — Audit for architecture-impacting PRs

## Architecture Guardrails

- Keep provider SDK code inside `src/runtime/*adapter*` only.
- Keep core orchestration provider-neutral (`src/core/` must not branch on provider name).
- Keep turn-ingress governance decisions server-side and non-bypassable (allow/deny/escalate with reason codes).
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
  - `docs/plans/tenant-tool-execution-architecture.md`
  - `docs/plans/docs-inventory-master.md` (when doc lifecycle status changes)

## Quality and Safety Gates

- Block merge for P0 architecture/safety failures.
- Require tests for happy path, failure path, and replay/retry behavior when relevant.
- Require correlation IDs in runtime paths for auditability.
- Keep architecture fitness checks passing:
  - `scripts/architecture/validate_layers.py`
  - `scripts/architecture/scan_forbidden_imports.py`
- Keep release-candidate signoff artifacts healthy:
  - `make rc-signoff`
  - `make rc-signoff-json`

## Commit Message Policy

- Commit messages must end with:
  - `Author: Savin I. Razvan`
  - `GitHub-User: @SavinRazvan`
- This format is enforced by:
  - `.cursor/rules/commit-trailer-format.mdc`

## Branching and Release Safety

- Always create a dedicated working branch before coding:
  - `feature/<scope>`, `fix/<scope>`, `chore/<scope>`
- Keep `main` stable and merge-ready; avoid direct implementation commits on `main`.
- Before merge, require:
  - tests and architecture checks passing
  - checklist/research status updates for implemented scope
  - docs maintenance review for architecture/workflow changes (`docs/operations/documentation-maintenance-checklist.md`)
- After merge, require workflow finalization:
  - sync local `main` with `origin/main`
  - clean local feature branch
  - ensure remote feature branch is removed
- Use `git push --force-with-lease` only for intentional history rewrites on your own branch.

## Skills and Agent Extensions

- Primary project skills location: `.cursor/skills/`
- Standards-friendly project skills location: `.agents/skills/`
- Keep skill names stable and use `SKILL.md` per skill directory.
- Maintainer PR workflow is defined in `.agents/skills/PR_WORKFLOW.md` and uses:
  - `.agents/skills/review-pr/SKILL.md`
  - `.agents/skills/prepare-pr/SKILL.md`
  - `.agents/skills/merge-pr/SKILL.md`
- PR artifact scripts require actor attribution:
  - `python scripts/pr/review.py --pr <id/url> --actor "Savin I. Razvan" --agents "review-pr"`
  - `python scripts/pr/prepare.py --pr <id/url> --actor "Savin I. Razvan" --agents "review-pr | prepare-pr"`
  - `python scripts/pr/merge.py --pr <id/url> --actor "Savin I. Razvan" --agents "review-pr | prepare-pr | merge-pr"`
- PR publish verification (before merge workflow):
  - `python scripts/pr/verify_publish.py --branch <current_branch>`

## Next Directions

Architecture-aligned implementation priorities are in `architecture-goals/NEXT_DIRECTIONS.md` (Tier 1: adapter portability; Tier 2: entitlement/monetization + governance ingress safety controls; Tier 3: customer API guide and deployment certification). Use it when starting a slice or deciding what to work on next.
