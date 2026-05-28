---
name: merge-pr
description: Final checks, merge via gh, merge.md, finalize git state.
disable-model-invocation: true
---

# Merge PR

**Goal:** Merge only when artifacts + gates are satisfied.

## Steps

1. **Check:**  
   `python scripts/pr/merge.py --pr <id|url> --actor "Savin I. Razvan" --agents "review-pr | prepare-pr | merge-pr" --check-only`  
   Add `--arch-impacting` if alignment artifacts are required (enforces both alignment files; produced by **`enterprise-auditor`** per `enterprise-architecture-audit` skill).
2. No unresolved BLOCKER/IMPORTANT or alignment **P0** without documented acceptance.
3. `python scripts/pr/verify_publish.py --branch <branch>` and `gh pr view --json headRefName,state`.
4. `gh pr merge <n> --merge` (or repo policy).
5. Note merge SHA: `gh api repos/.../pulls/<n> -q .merge_commit_sha` (or `gh pr view` if working).
6. **Record:**  
   `python scripts/pr/merge.py --pr <id|url> --actor "Savin I. Razvan" --agents "review-pr | prepare-pr | merge-pr" --merge-sha <sha>`  
   (same `--arch-impacting` if used above). Enrich `merge.md` with method + follow-ups.
7. **Finalize:** `git checkout main`; `python scripts/pr/finalize.py --branch <branch>`; prune remotes; confirm feature branch gone on origin.

**Detail:** `.agents/skills/PR_WORKFLOW.md`.
