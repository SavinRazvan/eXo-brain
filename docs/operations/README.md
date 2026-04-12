<!--
File: README.md
Path: docs/operations/README.md
Role: Index for operational runbooks and release execution documents.
Used By:
 - docs/README.md
 - Release and operations workflows
Depends On:
 - docs/operations/workflow-complete.md
 - docs/operations/agent-workflow-procedures.md
 - scripts/pr/README.md
 - docs/operations/release-candidate-signoff-checklist.md
 - docs/operations/byoc-failure-injection-playbook.md
 - docs/operations/byoc-artifact-integrity-dashboard.md
Notes:
 - UI readiness smoke guidance is historical unless a UI track is re-enabled.
-->

# Operations Index

## Maintainer workflow (git vs PR artifacts)

- `docs/operations/workflow-complete.md` — end-to-end PR checklist (commit trailers: **`AGENTS.md`** § Commits + **`.cursor/rules/commit-trailer-format.mdc`**)
- `docs/operations/agent-workflow-procedures.md` — gate dedup + **§3b** commit provenance (sync list when trailer policy changes)
- `scripts/pr/README.md` — what `review.py` / `prepare.py` / `merge.py` write under **`.local/workflow-artifacts/pr/`** vs git message trailers

## Active Runbooks

- `docs/operations/adapter-telemetry-dimensions.md` — log/metric dimensions for provider adapters
- `docs/operations/release-candidate-signoff-checklist.md`
- `docs/operations/byoc-failure-injection-playbook.md`
- `docs/operations/byoc-artifact-integrity-dashboard.md`
- `docs/operations/documentation-maintenance-checklist.md`
- `docs/operations/governance-reason-code-catalog.md` — reason-code maintenance contract and code search anchors (pairs with `docs/api/governance-preview-and-testing.md`)

## Historical Runbooks

- `docs/archive/operations/local-ui-readiness-smoke.md` (retired for API-first Option C)
