# `.agents/skills`

Standards-friendly skills location (alongside `.cursor/skills/`, which Cursor loads from git).

## Layout

Each skill: **`<skill-name>/SKILL.md`**.

## This repo

| Area | Where |
|------|--------|
| Implementation loop | `.cursor/skills/implementation-execution-loop/`, `.cursor/agents/implementer.md`, `implementation-workflow-governance.mdc` |
| Tests | `.cursor/skills/test-module-coverage/`, `.cursor/agents/test-runner.md` |
| **Maintainer PR** | **`PR_WORKFLOW.md`** + `review-pr` / `prepare-pr` / `merge-pr` / `audit-alignment` here |
| Scripts | `scripts/pr/review.py`, `prepare.py`, `merge.py`, `finalize.py`, `verify_publish.py` |

Live trackers (gitignored): **`.local/index-and-planning/current/*.md`**. Full map: **`docs/operations/local-workspace-layout.md`**. Handoff checklist: **`docs/operations/workflow-complete.md`** §F (not a duplicate file under `.local/`).
