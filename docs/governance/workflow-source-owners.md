<!--
File: workflow-source-owners.md
Path: docs/governance/workflow-source-owners.md
Role: Canonical ownership map for workflow surfaces (scripts vs docs vs agents).
Used By:
 - Maintainers resolving conflicts between README, rules, and skills
Depends On:
 - docs/operations/workflow-complete.md
 - scripts/pr/prepare.py
Notes:
 - Executable behavior wins over prose; prose must link to scripts instead of copying steps.
-->

# Workflow source owners

| Concern | Canonical owner | Consumers |
|---------|-------------------|-----------|
| Prepare gate **order** and commands | `scripts/pr/prepare.py` (`GATES`) | Rules, skills, `workflow-complete.md`, README |
| PR artifact **paths** | `scripts/pr/local_workflow_paths.py` | `review.py`, `prepare.py`, `merge.py`, rules |
| Merge preconditions | `scripts/pr/merge.py` | `merge-pr` skill |
| Post-merge cleanup | `scripts/pr/finalize.py` | `merge-pr` skill |
| Maintainer narrative order | `.agents/skills/PR_WORKFLOW.md` (local, often gitignored) | Humans |
| Durable maintainer checklist | `docs/operations/workflow-complete.md` | Everyone (versioned) |
| Audit / dedup rules | `docs/operations/agent-workflow-procedures.md` | Alignment + governance |
| Always-on enforcement | `.cursor/rules/*.mdc` | Cursor agents |
| Git **commit** trailers (`Author` / `GitHub-User` + optional `Assisted-by`) | `.cursor/rules/commit-trailer-format.mdc` | `AGENTS.md` § Commits, implementer / implementation skills |
| Repository orientation | `AGENTS.md`, `README.md` | All agents |

**Rule:** If text disagrees with `prepare.py` or `local_workflow_paths.py`, update the text in the **same PR** as the script change, or immediately after.
