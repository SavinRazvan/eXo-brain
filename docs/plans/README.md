<!--
File: README.md
Path: docs/plans/README.md
Role: Index and lifecycle map for planning documents.
Used By:
 - docs/README.md
 - Maintainers selecting canonical vs historical plans
Depends On:
 - docs/plans/docs-authority-map.md
 - docs/plans/docs-archive-index.md
Notes:
 - The canonical current-state plan is tenant-tool-execution-architecture.md.
-->

# Plans Index

For the **numbered architecture planes** (stack), see [`docs/architecture/ARCHITECTURE.md`](../architecture/ARCHITECTURE.md) §2. For how **plans** map to runtime layers and modules, see the same file §10.

## Canonical Current-State Plans

- `docs/plans/tenant-tool-execution-architecture.md`
- `docs/plans/option-c-contract-freeze.md`
- `docs/plans/option-c-worker-isolation-contract.md`
- `docs/plans/option-c-performance-gates.md`

## Documentation governance (active)

- `docs/plans/docs-inventory-master.md`
- `docs/plans/docs-authority-map.md`
- `docs/plans/docs-archive-index.md`
- `docs/plans/notebook-standards.md`

## Working product / execution plans

- `docs/plans/control-plane-product-alignment-plan.md` — control plane monetization narrative; integration surfaces (provider adapter vs API vs customer bridge). **Baseline doc slice (§2 checklist) closed** — see `docs/archive/plans/control-plane-product-alignment-baseline-slice-closed.md`; **L1–L4** still active in the plan file.
- `docs/plans/short-long-term-execution-plan.md` — short vs long horizons; main UI via APIs; diagrams §1.1 (mirrored in root `README.md`)
- `docs/plans/short-long-term-execution-plan.plan.md` — **implementer companion:** governance metadata, inlined non-breaking rules, workstreams W1–W4 + S4 (main UI), primary artifacts, rolling status hooks, pre/post checklists, slice boilerplate for `.local/.../plan.md` (canonical narrative: `short-long-term-execution-plan.md`)
- `docs/plans/adapter-packages-extraction-handoff.md` — adapter extraction checklist (`packages/` → separate repos)

## Archived plans (completed or superseded)

Closed execution waves live under **`docs/archive/plans/`** (non-authoritative). **`docs/plans/docs-archive-index.md`** lists each file and its **canonical replacement**.

Examples: enterprise audit remediation (phases 1–8), post–modular monolith roadmap, adapter/gateway hygiene plan + todos, northbound `/v1` design addendum, documentation cleanup master plan, docs/notebooks cleanup plan — plus older API platform / backlog snapshots also in that folder.
