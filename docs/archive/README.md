<!--
File: README.md
Path: docs/archive/README.md
Role: Defines archive folder structure and metadata contract for archived documentation.
Used By:
 - docs/plans/docs-archive-index.md
 - docs/plans/docs-authority-map.md
Depends On:
 - docs/plans/docs-inventory-master.md
Notes:
 - Archived docs are non-authoritative and retained for traceability.
-->

# Documentation Archive

## Purpose

`docs/archive/` stores superseded historical documents that should not be used as active implementation authority.

## Structure

- `docs/archive/plans/`
- `docs/archive/operations/`
- `docs/archive/results/`
- `docs/archive/roadmap/` (only when roadmap snapshots are explicitly archived)

## Required Archive Metadata

Each archived document must include:

- `Status: archived`
- `Canonical replacement: <path or N/A>`
- `Archived on: <YYYY-MM-DD>`
- `Archive reason: <superseded | obsolete | historical snapshot>`

## Rules

- Do not delete historical docs when superseded; move them into `docs/archive/<domain>/`.
- Update `docs/plans/docs-archive-index.md` in the same PR for every moved file.
- Keep active rules/skills/scripts pointing to canonical active docs, not archived docs.
