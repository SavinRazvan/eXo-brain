<!--
File: workflow-complete.md
Path: docs/operations/workflow-complete.md
Role: End-to-end maintainer workflow checklist (durable); complements gitignored `.agents/skills/PR_WORKFLOW.md`.
Used By:
 - Maintainers / local agents
Depends On:
 - .agents/skills/PR_WORKFLOW.md (canonical narrative + skill order; local copy when present)
 - docs/operations/agent-workflow-procedures.md (enterprise-auditor + dedup contract)
 - scripts/pr/README.md (PR scripts vs git commit trailers)
 - scripts/pr/review.py, scripts/pr/prepare.py, scripts/pr/merge.py, scripts/pr/finalize.py, scripts/pr/verify_publish.py
 - scripts/pr/check_testing_artifacts.py
 - scripts/architecture/check_governance_consistency.py (CI parity)
Notes:
 - Additive only: does not replace skills or scripts. Post-merge cleanup removes **git branches**, not docs.
-->

# Complete workflows (maintainer checklist)

## A) Standard PR slice (happy path)

1. **Branch** — `git checkout -b feature/<scope>` (or `fix/`, `chore/`).
2. **Implement + commit** — follow layer rules; commit trailers (required `Author` / `GitHub-User`, optional `Assisted-by`; no `Made-with:`) per `.cursor/rules/commit-trailer-format.mdc` and `AGENTS.md` § Commits.
3. **Push + PR** — `git push -u origin HEAD` → open PR to `main`.
4. **Publish checkpoint** (before merge workflow):
   - `python scripts/pr/verify_publish.py --branch "$(git branch --show-current)"`
   - `gh pr view --json number,url,headRefName,state,mergeStateStatus`
5. **Prepare + CI parity (before merge / push)** — **first four commands match `scripts/pr/prepare.py` `GATES` exactly (see `agent-workflow-procedures.md` §3):**
   - `python scripts/pr/check_testing_artifacts.py`
   - `python -m pytest -q` (CI also enforces **95%** `src/**` coverage via `COV_FAIL_UNDER`; use `pytest --cov=src --cov-fail-under=95` when touching risky areas)
   - `python scripts/architecture/validate_layers.py`
   - `python scripts/architecture/scan_forbidden_imports.py`
   - then **`python scripts/architecture/check_governance_consistency.py`** (CI job; run locally when changing governance/workflows)
6. **Skills order (do not skip)** — see `.agents/skills/PR_WORKFLOW.md`:
   - `review-pr` → `prepare-pr` → `merge-pr`
7. **Artifacts** (must exist before merge; fill with real content):
   - `.local/workflow-artifacts/pr/review.md` — `python scripts/pr/review.py --pr <id|url> --actor "Savin I. Razvan" --agents "review-pr"` then edit findings.
   - `.local/workflow-artifacts/pr/prep.md` — `python scripts/pr/prepare.py --pr ... --actor "..." --agents "review-pr | prepare-pr"` (runs gates unless `--skip-gates`).
   - `.local/workflow-artifacts/pr/merge.md` — produced via `merge-pr` / `scripts/pr/merge.py` when ready.
8. **Finalize after merge** (mandatory):
   - `git checkout main` && sync with `origin`
   - `python scripts/pr/finalize.py --branch <feature-branch>` (optional `--delete-merged-local`)
   - `git fetch --prune origin` and confirm remote branch gone if policy requires it.

## B) Architecture-impacting PRs (extra gates)

Before `/prepare-pr` / final merge:

1. Run **`enterprise-auditor`** with a **focused alignment pass** (`.cursor/skills/enterprise-architecture-audit/SKILL.md`; see `.agents/skills/PR_WORKFLOW.md`).
2. Ensure **both** exist (merge script enforces with `--arch-impacting`):
   - `.local/workflow-artifacts/alignment/alignment-audit.md`
   - `.local/workflow-artifacts/alignment/alignment-todos.md`
3. Use `python scripts/pr/merge.py --pr ... --actor "..." --agents "..." --arch-impacting` when recording merge readiness.

## C) Testing + planning index sync (medium/high risk)

Before final `/prepare-pr`:

1. Map changes → `tests/modules/<area>/`.
2. Follow `.cursor/skills/test-module-coverage/SKILL.md` (local) / test-runner agent profile.
3. Update `.local/index-and-planning/current/test-plan.md` and `test-index.md`.
4. Run `python scripts/pr/check_testing_artifacts.py`.

## D) Doc / plan sync (when scope shifts)

Follow **`agent-workflow-procedures.md` §5** (one `updates-log` entry; avoid duplicating gate lists).

Update tracked docs and local cockpit as needed:

- `docs/plans/tenant-tool-execution-architecture.md`, `docs/plans/docs-inventory-master.md` (if lifecycle changes)
- `.local/index-and-planning/current/plan.md`, `docs/architecture/workspace-architecture.md`, `.local/index-and-planning/current/work-tracker.md`, `.local/index-and-planning/history/updates-log.md`

## E) Release candidate (optional extended path)

When cutting an RC (maintainer operation):

- Follow `docs/operations/release-candidate-signoff-checklist.md` and `make rc-signoff` / `make rc-signoff-json` as documented in repo `Makefile` / release scripts.

## F) Implementer slice closure (before handoff)

This is the **implementation agent** end-of-loop on top of sections **C** and **D** — run it before saying a slice is finished:

1. **`.local/index-and-planning/history/updates-log.md`** — append one top entry (summary, validation, next step; no repeated prepare-gate paste — see **`agent-workflow-procedures.md`**).
2. **`.local/index-and-planning/current/work-tracker.md`** — resolve task status; keep one primary `in_progress` across the file.
3. **`test-plan.md` / `test-index.md`** — update when tests or ownership changed.
4. **`coverage-index.md`** — regenerate after any coverage run that matters for the slice (`coverage json` + `scripts/dev/generate_coverage_index.py`).
5. **`implementation-control-center.html`** — under `.local/agents-control-center/dashboards/`; if you add a tracker, update **`../config/pages.json`** and header **Depends On** comments; keep **Coverage** in sync with **`coverage-index.md`**.
6. **`module-audit.html`** — under `.local/agents-control-center/audits/`; touch only when deliberately refreshing a deep module audit export, not per slice.

Canonical detail: **`.local/index-and-planning/current/plan.md`** section **Implementer slice closure (mandatory end-of-loop)**.

## File retention policy (explicit)

- **Do not delete** workflow sources: `.agents/skills/**`, versioned `.cursor/rules`, `.cursor/agents`, `.cursor/skills` (see `.gitignore` exceptions), tracked `scripts/pr/**`, or this checklist.
- **Do delete** (when appropriate): merged **git branches** only, via `finalize.py` / GitHub auto-delete — not markdown artifacts you still need for history (archive in `docs/archive/` instead if superseded).

## Canonical copies (avoid drift)

- Procedures + dedup rules: **`agent-workflow-procedures.md`**
- Skill order + finalization: **`.agents/skills/PR_WORKFLOW.md`**
- Prepare gate list: **`scripts/pr/prepare.py`** (`GATES`)
- CI shape: **`.github/workflows/architecture-fitness.yml`**

If this file and `PR_WORKFLOW.md` or `prepare.py` disagree, **fix this file** to match the script/workflow truth.
