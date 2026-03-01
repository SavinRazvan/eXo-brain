# PR Workflow For eXo-brain

This file is the maintainer source of truth for PR handling in this repository.

## Required Skill Order

Use these skills in sequence:

1. `review-pr` (review only, no code changes)
2. `prepare-pr` (apply fixes, run gates, update docs/checklists)
3. `merge-pr` (merge only after all checks pass)

Do not skip steps.

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
  - `Action-By: @<github_username>`
  - `GitHub-Profile: https://github.com/<github_username>`
  - role labels by phase (`Reviewed-By`, `Prepared-By`, `Merged-By`)

## Alignment Audit Checkpoint (Advisory)

For architecture-impacting PRs (module boundaries, runtime/policy workflow changes, test/CI path moves, or roadmap/rule updates):

- run the advisory audit skill before `/prepare-pr`
- classify findings with `docs/roadmap/alignment-audit-schema.md`
- block `/prepare-pr` on unresolved `P0` findings unless explicitly accepted with rationale
- include unresolved `P1/P2` items in reconciliation TODOs with owner and next slice
