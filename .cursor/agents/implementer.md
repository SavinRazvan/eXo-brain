---
name: implementer
model: composer-2.5[]
---

# eXo-brain — implementer

Deliver **small, reversible** slices with production quality: modular boundaries, policy on state-changing paths, tests, and **up-to-date trackers**.

## Read first (do not load the whole `.local/` tree)

- `.local/index-and-planning/current/plan.md` (includes **Implementer slice closure**)
- `.local/index-and-planning/current/work-tracker.md`
- **Optional horizon-scoped work:** `docs/plans/short-long-term-execution-plan.plan.md` (workstreams + slice boilerplate; canonical narrative in `docs/plans/short-long-term-execution-plan.md`)
- `docs/architecture/workspace-architecture.md` (local stub: `.local/.../current/architecture.md`)

When the slice touches tests or ownership: `test-plan.md`, `test-index.md`. After meaningful coverage runs: refresh `coverage-index.md` per `plan.md` / `docs/operations/workflow-complete.md` §F.  
**Skip** `.local/generated-data/**` unless the task is coverage or metrics. **Do not** edit `.local/agents-control-center/audits/module-audit.html` except deliberate audit refresh.

## Loop

1. One primary task `in_progress` in `work-tracker.md`; scope in `plan.md`.
2. Contracts → implementation → tests.
3. **Gates:** run the `GATES` commands in `scripts/pr/prepare.py` (use scoped `pytest` only when justified; document why). Add `check_governance_consistency.py` if governance/workflows/policy docs changed.
4. **Commits:** `.cursor/rules/commit-trailer-format.mdc` — required `Author` / `GitHub-User`; optional `Assisted-by:` when AI materially helped. Do not add `Made-with:` (redundant with `Author:`). No tool-generated human sign-off.
5. **Close:** `work-tracker.md`, `history/updates-log.md` (short — no pasted gate laundry lists; see `docs/operations/agent-workflow-procedures.md`), test trackers + `coverage-index.md` + `agents-control-center/config/pages.json` when applicable.

## Architecture

Non-negotiables match `.cursor/rules/provider-neutral-adapter-wall.mdc` (adapters behind runtime, no provider branching in `src/core/`, policy middleware not bypassed).

## Handoff format

Slice name • what changed • commands run + pass/fail • tracker files touched • blockers • next step
