# PR Workflow For eXo-brain

This file is the maintainer source of truth for PR handling in this repository.

## Required Skill Order

Use these skills in sequence:

1. `review-pr` (review only, no code changes)
2. `prepare-pr` (apply fixes, run gates, update docs/checklists)
3. `merge-pr` (merge only after all checks pass)

Do not skip steps.

## Required Finalization Step (After Merge)

After `/merge-pr` completes, always close the workflow with repository cleanup:

1. `git checkout main`
2. `python scripts/pr/finalize.py --branch <feature-branch>`
3. optional hygiene pass for merged locals:
   - `python scripts/pr/finalize.py --branch <feature-branch> --delete-merged-local`
4. confirm remote feature branch is deleted:
   - `git ls-remote --heads origin <feature-branch>` (expect no output)
5. verify final state with `git status --short --branch` on `main`
6. ensure stale remote-tracking refs are pruned:
   - `git fetch --prune origin`

This finalization step is mandatory for workflow completion.

## Repository Hygiene Baseline

Keep GitHub auto-delete on merge enabled to avoid stale remote branch buildup:

1. check setting:
   - `gh api repos/SavinRazvan/eXo-brain --jq '.delete_branch_on_merge'`
2. if false, enable it:
   - `gh api -X PATCH repos/SavinRazvan/eXo-brain -f delete_branch_on_merge=true`

## Required Publish Checkpoint (After Commit, Before Merge)

After `commit -> push -> PR create`, verify publication and linkage deterministically:

1. `git push -u origin HEAD`
2. `python scripts/pr/verify_publish.py --branch "$(git branch --show-current)"`
3. `gh pr view --json number,url,headRefName,state,mergeStateStatus`
4. `gh pr checks --watch` (or `gh pr checks` if a non-blocking check is desired)

If upstream tracking is missing, run:

- `git branch --set-upstream-to=origin/<branch> <branch>`

Do not proceed to `/merge-pr` unless branch publication and PR linkage are both verified.

## Maintainer Quality Bar

- Validate the problem before accepting the proposed fix.
- Prefer provider-neutral, modular solutions over quick patches.
- Keep state-changing/high-impact paths policy-governed and auditable.
- Reject changes that bypass architecture boundaries.

## Required Verification Before Merge

Run at minimum:

- `python scripts/pr/check_testing_artifacts.py`
- `python -m pytest -q`
- `python scripts/architecture/validate_layers.py`
- `python scripts/architecture/scan_forbidden_imports.py`

For medium/high-risk module changes, include:

- `pytest --cov=src --cov-report=term-missing -q`

## Module Testing Agent Invocation Pattern

Before `/prepare-pr`, run module-focused testing through the testing specialist flow:

1. Map changed modules to `tests/modules/<module>/`.
2. Invoke `test-runner` using `.cursor/skills/test-module-coverage/SKILL.md`.
3. Ensure updates are recorded in:
   - `.local/control-center/test-plan.md`
   - `.local/control-center/test-index.md`
4. Remove/update obsolete tests when modules/contracts changed.
5. Run `python scripts/pr/check_testing_artifacts.py` before final `/prepare-pr`.

## Required Tracking Sync

If PR scope changes architecture/runtime status, update:

- `docs/plans/tenant-tool-execution-architecture.md`
- `.local/control-center/plan.md`
- `.local/control-center/architecture.md`
- `.local/control-center/work-tracker.md`
- `.local/control-center/test-plan.md`
- `.local/control-center/test-index.md`
- `docs/plans/docs-inventory-master.md` (if doc lifecycle status changes)

## Documentation Maintenance Checklist

For architecture-impacting or workflow-impacting PRs, run documentation checks during `/prepare-pr`:

1. Validate canonical docs are updated (`README.md`, docs indexes, module docs when relevant).
2. Verify no contradictions with:
   - `.cursor/rules/*.mdc`
   - this PR workflow file
   - `docs/plans/docs-authority-map.md`
3. If a document is superseded, move it to `docs/archive/<domain>/`, mark it archived, and add replacement in `docs/plans/docs-archive-index.md` in the same PR.
4. Optionally run:
   - `python scripts/docs/check_docs_metadata.py`
5. Record documentation updates in `.local/prep.md`.

## Required PR Artifacts

The flow should produce these local artifacts:

- `.local/review.md`
- `.local/prep.md`
- `.local/merge.md`
- `.local/alignment-audit.md` (required for architecture-impacting PRs)
- `.local/alignment-todos.md` (required for architecture-impacting PRs)

Each file should include:

- scope
- decisions/findings
- verification evidence
- remaining risks or follow-ups
- action attribution:
  - `Action-By: Savin I. Razvan`
  - `GitHub-User: @SavinRazvan`
  - `Agent/s: <agent-name-or-pipeline>`
  - role labels by phase (`Reviewed-By: Savin I. Razvan`, `Prepared-By: Savin I. Razvan`, `Merged-By: Savin I. Razvan`)

## Alignment Audit Checkpoint (Advisory)

For architecture-impacting PRs (module boundaries, runtime/policy workflow changes, test/CI path moves, or roadmap/rule updates):

- run the advisory audit skill before `/prepare-pr`
- classify findings with `docs/roadmap/alignment-audit-schema.md`
- block `/prepare-pr` on unresolved `P0` findings unless explicitly accepted with rationale
- include unresolved `P1/P2` items in reconciliation TODOs with owner and next slice
