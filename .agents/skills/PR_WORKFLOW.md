# PR workflow (maintainer)

**Implementer work** (trackers, slices) uses `.local/index-and-planning/current/*`, `.cursor/agents/implementer.md`, and `.cursor/rules/implementation-workflow-governance.mdc`. Slice closure: `docs/operations/workflow-complete.md` §F.

This file is the **merge path** only: **review → prepare → merge** (skills under `.agents/skills/<name>/`).

## Order

1. `review-pr` — findings only; run alignment audit when scope is architecture-impacting (`.cursor/rules/advisory-audit-alignment-enforcement.mdc`).
2. `prepare-pr` — fixes + `prepare.py` (runs `GATES` from `scripts/pr/prepare.py`).
3. `merge-pr` — `merge.py` check, `gh pr merge`, finalize repo state.

Per-step detail: the matching `SKILL.md` files in this directory (keep them as the short checklist).

## After push (before merge)

- `python scripts/pr/verify_publish.py --branch "$(git branch --show-current)"`
- `gh pr view --json number,url,headRefName,state` (fix upstream with `git branch --set-upstream-to=origin/<branch> <branch>` if needed)

## Gates (do not duplicate elsewhere)

Authoritative list: **`GATES` in `scripts/pr/prepare.py`**. Add **`python scripts/architecture/check_governance_consistency.py`** when changing governance, workflows, or tracked policy docs. For substantive `src/**` work, align with repo CI (**`pytest --cov=src --cov-fail-under=100`** when that is the project bar).

## Artifacts (under `.local/`)

| Phase | Path |
|-------|------|
| Review | `workflow-artifacts/pr/review.md` |
| Prepare | `workflow-artifacts/pr/prep.md` |
| Merge | `workflow-artifacts/pr/merge.md` |
| Alignment (when required) | `workflow-artifacts/alignment/alignment-audit.md`, `alignment-todos.md` |

Attribution in each: `Action-By: Savin I. Razvan`, `GitHub-User: @SavinRazvan`, `Agent/s: …`, plus `Reviewed-By` / `Prepared-By` / `Merged-By` as applicable. Paths: `scripts/pr/local_workflow_paths.py`.

## After merge (mandatory)

1. `git checkout main` && `git fetch --prune origin`
2. `python scripts/pr/finalize.py --branch <feature-branch>` (optional: `--delete-merged-local`)
3. `git ls-remote --heads origin <feature-branch>` → empty
4. `git status --short --branch`

Optional: enable `delete_branch_on_merge` on the GitHub repo (`gh api repos/<owner>/<repo> -q .delete_branch_on_merge`).

## Hygiene

- Prefer **one** stacked PR from the tip branch when commits are strictly linear (avoids duplicate merges).
- Reject bypasses of adapter wall / policy / tests. Doc updates for architecture-impacting PRs: `docs/operations/documentation-maintenance-checklist.md` and indexes as needed.

## Tracking when scope shifts

Update whatever actually changed among: `docs/plans/tenant-tool-execution-architecture.md`, `.local/index-and-planning/current/plan.md`, `work-tracker.md`, test trackers, `docs/plans/docs-inventory-master.md`.
