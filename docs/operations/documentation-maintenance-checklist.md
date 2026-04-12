<!--
File: documentation-maintenance-checklist.md
Path: docs/operations/documentation-maintenance-checklist.md
Role: Recurring checklist and ownership cadence to prevent documentation drift.
Used By:
 - .agents/skills/PR_WORKFLOW.md
 - Maintainers during PR preparation and release readiness
Depends On:
 - docs/plans/docs-authority-map.md
 - docs/plans/docs-inventory-master.md
 - scripts/docs/check_docs_metadata.py
Notes:
 - This checklist is lightweight and should be applied to architecture-impacting changes at minimum.
-->

# Documentation Maintenance Checklist

## Trigger

Run this checklist when a PR changes architecture, runtime contracts, policies, API routes/schemas, tenancy behavior, or release workflow instructions.

## PR Checklist (required)

- [ ] Confirm canonical docs impacted by the change are updated (`README`, plans, operations, module docs).
- [ ] Verify no contradictions against:
  - `.cursor/rules/*.mdc`
  - `.agents/skills/PR_WORKFLOW.md`
  - `docs/plans/docs-authority-map.md`
- [ ] If you touch **git commit / AI provenance** policy or release provenance wording: sync every surface listed in **`docs/operations/agent-workflow-procedures.md` §3b** (includes `docs/plans/docs-inventory-master.md` rows for indexed paths, `configs/release/README.md`, `scripts/pr/README.md`, `docs/releases/RELEASE_TEMPLATE.md`, and this checklist when it references that policy).
- [ ] If a doc is superseded, move it to `docs/archive/<domain>/`, mark it `archived`, and add replacement pointer.
- [ ] Update `docs/plans/docs-inventory-master.md` when status changes (`active`, `planned`, `archived`).

## Optional Lint Check

Run:

```bash
python scripts/docs/check_docs_metadata.py
```

This verifies required docs indexes and required sections for P0 module docs.

## Ownership and Cadence

| Area | Owner | Cadence | Minimum output |
|---|---|---|---|
| Canonical architecture and plans docs | Savin I. Razvan | Quarterly + after major slices | Updated canonical status and replacement pointers |
| Operations runbooks | Savin I. Razvan | Quarterly + before release candidates | Updated operator checklist and gate references |
| Module docs (`docs/modules/*`) | Savin I. Razvan | Quarterly + per module contract change | Updated code/tests links and boundary notes |

## Evidence

For major cleanup slices, publish a short evidence summary under `artifacts/evidence/` describing:

- files updated
- archived mappings added
- contradiction fixes applied
- optional lint output (if run)
