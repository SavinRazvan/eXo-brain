<!--
File: RELEASE_TEMPLATE.md
Path: docs/releases/RELEASE_TEMPLATE.md
Role: Template for release candidate and production rollout notes.
Used By:
 - .github/workflows/release-candidate.yml
Depends On:
 - artifacts/evidence/*
Notes:
 - Keep this file synchronized with CI/CD governance rules.
-->

# Release Template

## Metadata
- Release ref:
- Release date:
- Prepared by:
- Approved by:

## Gate Summary
- Automated tests (`pytest -q`):
- Architecture checks:
- Forbidden import checks:
- Contract/integration checks:

## Evidence Bundle
- Gate evidence artifact:
- Provenance artifact: (RC / CI runner metadata — **not** the same as git commit trailers; see **`AGENTS.md`** § Commits and **`.cursor/rules/commit-trailer-format.mdc`**: `Author` / `GitHub-User`, optional `Assisted-by`; **no `Made-with:`**)
- Deploy evidence artifact:

## Rollout Plan
- Environment order: `stage -> prod`
- Strategy: `canary -> progressive`
- Rollback owner:
- Rollback command:

## Risks and Follow-Ups
- Known risks:
- Post-release follow-up issues:
