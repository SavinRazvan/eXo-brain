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
2. `git pull --ff-only origin main`
3. `git branch -d <feature-branch>` (if present)
4. confirm remote feature branch is deleted (via `gh pr view` or `git ls-remote --heads origin <feature-branch>`)
5. verify final state with `git status --short --branch` on `main`

This finalization step is mandatory for workflow completion.

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

- `python -m pytest -q`
- `python scripts/architecture/validate_layers.py`
- `python scripts/architecture/scan_forbidden_imports.py`

## Required Tracking Sync

If PR scope changes architecture/runtime status, update:

- `.cursor/research-for-refactor/12-bootstrap-checklist.md`
- `.cursor/research-for-refactor/06-mvp-build-sequence.md`

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
