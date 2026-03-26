<!--
File: README.md
Path: docs/governance/README.md
Role: Index for documentation governance and IA charters.
Used By:
 - docs/README.md
Depends On:
 - docs/plans/docs-authority-map.md
Notes:
 - Keep entries aligned with docs-inventory-master rows.
-->

# Governance documentation

- [folder-charter.md](folder-charter.md) — `docs/` vs `.local/` purpose boundaries
- [path-migration-map.md](path-migration-map.md) — old → new paths
- [workflow-source-owners.md](workflow-source-owners.md) — script-first ownership
- [drift-prevention.md](drift-prevention.md) — lightweight alignment process
- [rollout-phases.md](rollout-phases.md) — rollout notes
- [rules-overlap-matrix.md](rules-overlap-matrix.md) — Cursor rules inventory (Track D)

## Product vocabulary (strategy alignment)

When docs mention **control plane**, **customer bridge**, **provider runtime adapter**, or monetization on **governance** (not raw LLM resale), keep them consistent across:

- [`docs/strategy/README.md`](../strategy/README.md) (index)
- [`docs/strategy/governed-execution-positioning.md`](../strategy/governed-execution-positioning.md) (canonical table of three integration surfaces)
- [`docs/plans/control-plane-product-alignment-plan.md`](../plans/control-plane-product-alignment-plan.md) (phased plan + discussion agenda)
- [`docs/strategy/traceability-matrix.md`](../strategy/traceability-matrix.md) (decision → code mapping)
- [`docs/api/customer-api-integration-guide.md`](../api/customer-api-integration-guide.md) (customer-facing contracts, including optional `/v1`)

Architecture cross-links: [`docs/architecture/ARCHITECTURE.md`](../architecture/ARCHITECTURE.md), [`docs/architecture/workspace-architecture.md`](../architecture/workspace-architecture.md).
