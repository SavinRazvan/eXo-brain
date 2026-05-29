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
- [ ] If `notebooks/**` or notebook builders change: sync `notebooks/README.md`, `notebooks/EVALUATOR_GUIDE.md`, and `docs/plans/notebook-standards.md`; re-run affected notebooks for outputs; confirm `docs/architecture/governed-execution-pipeline.md` **Hands-on proof** still matches `tutorial_08` when that lab changes.
- [ ] If adapter PyPI versions change: sync `requirements.txt` / `requirements-adapters.txt`, `docs/operations/adapter-installation.md`, `docs/handoffs/exo_adapters_pypi_handoff.md`, and [eXo_adapters CHANGELOG](https://github.com/SavinRazvan/eXo_adapters/blob/main/CHANGELOG.md) as applicable.
- [ ] If `src/api/routers/**` paths or mounts change: sync `docs/api/customer-api-integration-guide.md`, `docs/api/README.md`, and `docs/modules/api.md`; spot-check `docs/strategy/foundation-tier-adoption-checklist.md` step table.
- [ ] If `src/core/`, `src/runtime/`, `src/tools/`, `src/policies/`, or `src/tenancy/` contracts change: update the matching `docs/modules/*.md` (and `docs/modules/README.md` map if ownership shifts); run `python scripts/docs/check_docs_metadata.py`.
- [ ] If alignment audit categories, merge-gate expectations, or hardening program phases change: sync `docs/roadmap/*` and `.cursor/skills/enterprise-architecture-audit/SKILL.md` references to `alignment-audit-schema.md`.
- [ ] If tiers, entitlements, adapter versions, or product boundaries change: sync `docs/strategy/entitlement-matrix.md`, `adapter-compatibility-matrix.md`, `traceability-matrix.md`, `next-directions.md`, and `docs/api/customer-api-integration-guide.md`.
- [ ] If workflow gates, `.cursor/rules`, PR artifact paths, or doc IA change: sync `docs/governance/workflow-source-owners.md`, `docs/governance/drift-prevention.md`, `docs/governance/rules-overlap-matrix.md`, and run `python scripts/architecture/check_governance_consistency.py`.
- [ ] If `src/runtime/*`, `src/mcp/*`, plugin managers, or `workflow_loader` behavior changes: sync `docs/runtime_contracts.md`, `docs/mcp_integration.md`, `docs/plugin_lifecycle.md`, `docs/workflow_loading.md`, and `docs/modules/*` as needed.
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
