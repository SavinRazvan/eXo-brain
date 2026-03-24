# AGENTS.md

## Project intent

`eXo-brain` is a provider-neutral AI orchestration platform. **AI as a commodity**: providers are pluggable adapters, not orchestration owners. Delivery posture: API-first (control + adapter + data planes); UI/dashboard deferred unless re-enabled.

## First reads (onboarding)

1. `README.md` — architecture map, request/turn flows  
2. `docs/strategy/next-directions.md` — priorities  
3. `docs/strategy/goal.md` — boundary, non-negotiables  
4. `docs/strategy/entitlement-matrix.md` — tiers  

Abbreviations: `docs/operations/abbreviations-notepad.md`  
Gitignored workspace map: **`docs/operations/local-workspace-layout.md`** (what lives under `.local/`, what to open vs ignore).

## Rules (always applied in Cursor)

| Rule | Topic |
|------|--------|
| `.cursor/rules/provider-neutral-adapter-wall.mdc` | Layers, adapters, policy |
| `.cursor/rules/implementation-workflow-governance.mdc` | Slice lifecycle, `.local/.../current` trackers, tests |
| `.cursor/rules/pr-workflow-enforcement.mdc` | PR-first, artifacts, branch safety |
| `.cursor/rules/commit-trailer-format.mdc` | Commit trailers |
| `.cursor/rules/file-docstring-header-relations.mdc` | File headers |
| `.cursor/rules/local-artifact-protection.mdc` | `.exo_data/`, `.coverage` |
| `.cursor/rules/advisory-audit-alignment-enforcement.mdc` | Alignment audits when scope warrants |

Architecture detail: same themes as the adapter-wall rule (provider SDK only in `src/runtime/*adapter*`, core provider-neutral, deterministic tool paths, typed boundaries). **Do not duplicate long gate lists** in chat or `updates-log.md` — say *prepare gates green* or paste failing command output only.

## Execution workflow

Sequence: `plan → interfaces → implementation → tests → evidence → docs update`.  
Incremental slices; sync status with:

- `docs/plans/tenant-tool-execution-architecture.md`
- `.local/index-and-planning/current/plan.md`, `work-tracker.md`, `test-plan.md`, `test-index.md`
- `docs/architecture/workspace-architecture.md` (stub: `.local/.../current/architecture.md`)
- `docs/plans/docs-inventory-master.md` when doc lifecycle changes

Full handoff checklist: `docs/operations/workflow-complete.md` (esp. §F).

## Quality gates (single source of truth)

**Default merge gate order** is the `GATES` list in **`scripts/pr/prepare.py`** (today: `check_testing_artifacts.py`, `pytest -q`, `validate_layers.py`, `scan_forbidden_imports.py`).  
Add **`python scripts/architecture/check_governance_consistency.py`** when changing governance, workflows, or tracked policy docs (CI mirrors this).  
Substantive `src/**` work in this repo: use **`pytest --cov=src --cov-fail-under=100`** (or project CI parity) before merge.

RC helpers: `make rc-signoff`, `make rc-signoff-json`.

## Commits

End message body with:

- `Author: Savin I. Razvan`
- `GitHub-User: @SavinRazvan`

(`.cursor/rules/commit-trailer-format.mdc`.)

## Branching

Use `feature/`, `fix/`, or `chore/` branches; keep `main` merge-ready. After merge: sync `main` with `origin/main`, remove local + remote feature branch. `git push --force-with-lease` only for intentional rewrites on your branch.

## Skills and agents (where to look)

| Role | Entry |
|------|--------|
| Implement | `.cursor/agents/implementer.md` + `.cursor/skills/implementation-execution-loop/SKILL.md` |
| Tests / coverage | `.cursor/agents/test-runner.md` + `.cursor/skills/test-module-coverage/SKILL.md` |
| Verify claims | `.cursor/agents/verifier.md` |
| Deep module map | `.cursor/skills/audit-module-map/SKILL.md` |
| Maintainer PR | `.agents/skills/PR_WORKFLOW.md` → `review-pr` → `prepare-pr` → `merge-pr` (versioned under `.agents/skills/`, same layout as Cursor skills) |

Scripts (attribution use your name as today):

- `python scripts/pr/verify_publish.py --branch <branch>`
- `python scripts/pr/review.py|prepare.py|merge.py --pr <id|url> --actor "Savin I. Razvan" --agents "<pipeline>"`

## Next work

`docs/strategy/next-directions.md` (Tier 1–3 priorities).
