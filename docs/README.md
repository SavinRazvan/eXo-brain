<!--
File: README.md
Path: docs/README.md
Role: Top-level documentation index for active, planned, and archived content.
Used By:
 - README.md
 - Maintainers and contributors navigating repository documentation
Depends On:
 - docs/plans/docs-inventory-master.md
 - docs/plans/docs-authority-map.md
 - scripts/pr/README.md
Notes:
 - Keep this file concise and update links whenever doc status changes.
-->

# Documentation index

## Reading spine (recommended)

1. `README.md` (repository entry)
2. `docs/strategy/goal.md` + `docs/strategy/next-directions.md` (direction) + `docs/plans/short-long-term-execution-plan.md` (**short vs long horizons** and main-UI attach)
3. `docs/architecture/ARCHITECTURE.md` (numbered planes + **control/adapter/data plane** vocabulary map in §2)
3b. `docs/architecture/governed-execution-pipeline.md` (entitlements → ingress → orchestrator → tool policy → deterministic execution)
4. `docs/architecture/beginner-workflow.md` (plain-language walkthrough)
5. `docs/architecture/mvp.md` + `docs/architecture/workspace-architecture.md` (shape detail)
6. `docs/plans/tenant-tool-execution-architecture.md` (implementation status)
7. `docs/operations/workflow-complete.md` (maintainer path)
8. `docs/operations/local-workspace-layout.md` (gitignored `.local/` contract)

## Hands-on validation (notebooks)

Narrative and smoke evidence for evaluators and contributors — **not** a substitute for `pytest`.

| Entry | Role |
|---|---|
| [notebooks/README.md](../notebooks/README.md) | Full index (15 notebooks), build scripts, per-notebook detail |
| [notebooks/EVALUATOR_GUIDE.md](../notebooks/EVALUATOR_GUIDE.md) | Time-boxed paths (15 min / 90 min / security / maintainer smoke) |
| [docs/plans/notebook-standards.md](plans/notebook-standards.md) | Regeneration contract, structure, CI, ownership map |
| [docs/architecture/governed-execution-pipeline.md](architecture/governed-execution-pipeline.md) | Production turn ordering; **Hands-on proof** ↔ `tutorial_08` |

**Learning order:** `tutorial_01` → `02` → `03` → `04`; then `05`–`07` as needed; `tutorial_08` for the local governance lab; `tutorial_09` for optional live contrasts.

## Strategy (`docs/strategy/`)

- [`docs/strategy/README.md`](strategy/README.md) — index, reading order, shipped vs planned snapshot
- [governed-execution-positioning.md](strategy/governed-execution-positioning.md) — product boundary, ICP, four-layer model
- [entitlement-matrix.md](strategy/entitlement-matrix.md) + [traceability-matrix.md](strategy/traceability-matrix.md) — tiers and code anchors
- [adapter-compatibility-matrix.md](strategy/adapter-compatibility-matrix.md) — PyPI **0.1.1** lockstep packages
- [next-directions.md](strategy/next-directions.md) — prioritized implementation directions
- [customer-self-serve-governance-journey.md](strategy/customer-self-serve-governance-journey.md) — self-serve spine

> Root `architecture-goals/` was retired; **edit `docs/strategy/*`** for all strategy content.

## Architecture (`docs/architecture/`)

- `docs/architecture/README.md`
- `docs/architecture/ARCHITECTURE.md` — ten planes; **§2** maps strategy terms (control / governance / adapter / data plane, interface Layer A|B) to code
- `docs/architecture/beginner-workflow.md` — beginner-friendly workflow and analogy guide
- `docs/architecture/mvp.md` — layers and flows
- `docs/architecture/workspace-architecture.md` — workspace doctrine
- `docs/architecture/governed-execution-pipeline.md` — canonical governed turn ordering and direct-`Orchestrator` bypass note
- `docs/plans/notebook-standards.md` — notebook categories, builders, CI (`tutorial_08` nbconvert)

## Notebooks (repo root)

- `notebooks/README.md`, `notebooks/EVALUATOR_GUIDE.md` — see **Hands-on validation** above

## Decisions (`docs/decisions/`)

- [docs/decisions/README.md](decisions/README.md) — ADR-style index
- [submit-tool-results-orchestrator-only.md](decisions/submit-tool-results-orchestrator-only.md) — OpenAI adapter continuation model

## Handoffs (`docs/handoffs/`)

- [docs/handoffs/README.md](handoffs/README.md) — completed missions + pointers
- [exo_adapters_pypi_handoff.md](handoffs/exo_adapters_pypi_handoff.md) — **adapter packages on PyPI** → [adapter-installation.md](operations/adapter-installation.md)

## Adapter packages (PyPI)

- [eXo_adapters on GitHub](https://github.com/SavinRazvan/eXo_adapters) — adapter authoring, tests, releases (no in-tree mirror in eXo-brain)
- [docs/operations/adapter-installation.md](operations/adapter-installation.md) — operator `pip install` + `adapter_class_ref`
- [docs/operations/adapter-repos-and-pypi.md](operations/adapter-repos-and-pypi.md) — one repo, four wheels

## Governance (`docs/governance/`)

- [`docs/governance/README.md`](governance/README.md) — index: charter, source owners, drift prevention, rules matrix
- [folder-charter.md](governance/folder-charter.md) — `docs/` vs `.local/` vs repo-root assets
- [workflow-source-owners.md](governance/workflow-source-owners.md) — `prepare.py` / artifact paths win over prose
- [drift-prevention.md](governance/drift-prevention.md) — post-change checklists (gates, trailers, API docs)
- [path-migration-map.md](governance/path-migration-map.md) — legacy → nested `.local/` paths

## Root technical contracts

Short, stable references at `docs/` root (detail in `docs/modules/` and `docs/architecture/`):

| Document | Role |
|---|---|
| [runtime_contracts.md](runtime_contracts.md) | `RuntimeAdapter` ABC (PyPI contracts), mode selection, northbound vs southbound |
| [mcp_integration.md](mcp_integration.md) | MCP trust/health, policy-gated adapter (module tested; not default API path) |
| [plugin_lifecycle.md](plugin_lifecycle.md) | Tool + agent in-process plugin managers |
| [workflow_loading.md](workflow_loading.md) | `WorkflowLoader` JSON/YAML registry (tested; orchestration wiring TBD) |
| [architecture_mvp.md](architecture_mvp.md) | Redirect → [architecture/mvp.md](architecture/mvp.md) |

## Active canonical docs
- `docs/plans/tenant-tool-execution-architecture.md`
- `docs/plans/option-c-contract-freeze.md`
- `docs/plans/option-c-worker-isolation-contract.md`
- `docs/plans/option-c-performance-gates.md`
- `docs/operations/release-candidate-signoff-checklist.md`
- `docs/operations/byoc-failure-injection-playbook.md`
- `docs/operations/byoc-artifact-integrity-dashboard.md`
- `docs/operations/documentation-maintenance-checklist.md`
- `configs/release/README.md` — release threshold bundle + pointer to commit provenance vs RC artifacts
- `scripts/pr/README.md` — PR phase scripts vs git commit trailers (`Author` / `GitHub-User`, optional `Assisted-by`; no `Made-with:`)

## Operations (workflows)

- `docs/operations/workflow-complete.md`
- `docs/operations/agent-workflow-procedures.md`
- `docs/operations/local-workspace-layout.md`
- `docs/operations/abbreviations-notepad.md` — glossary (**Option C** = control + adapter + data plane); full mapping in `docs/architecture/ARCHITECTURE.md` §2

## Planning and cleanup governance

- `docs/plans/docs-inventory-master.md`
- `docs/plans/docs-authority-map.md`
- `docs/plans/docs-archive-index.md`
- `docs/plans/short-long-term-execution-plan.md` — execution horizons (diagrams + tier emphasis)
- `docs/plans/README.md`

## Module docs

- [`docs/modules/README.md`](modules/README.md) — P0 index (`core`, `runtime`, `tools`, `policies`, `tenancy`, `api`), map to `src/` and tests
- Maintainer lint: `python scripts/docs/check_docs_metadata.py`

## Roadmap (alignment + hardening)

- [`docs/roadmap/README.md`](roadmap/README.md) — index: alignment audit schema/templates, module hardening program
- [`docs/roadmap/alignment-audit-schema.md`](roadmap/alignment-audit-schema.md) — finding shape for `.local/workflow-artifacts/alignment/`
- [`docs/roadmap/enterprise-module-hardening-integration-plan.md`](roadmap/enterprise-module-hardening-integration-plan.md) — phased `src/*` hardening tracker
- [`docs/roadmap/module-hardening-slice-checklist.md`](roadmap/module-hardening-slice-checklist.md) — per-PR checklist

## API docs

- [`docs/api/README.md`](api/README.md) — index, `/tenants` path convention, reading order
- [`docs/api/customer-api-integration-guide.md`](api/customer-api-integration-guide.md) — tier-aware endpoints and examples (v1.9.0+ uses full `/tenants/...` paths)
- **Planned in-tree:** `docs/api/governance-preview-and-testing.md` — safe iteration, audit correlation, planned simulation APIs (see `traceability-matrix.md`)

## Customer self-serve governance (strategy + plans)

- `docs/strategy/customer-self-serve-governance-journey.md` — product contract and agent rules
- `docs/strategy/foundation-tier-adoption-checklist.md` — Foundation onboarding steps
- `docs/plans/governance-configuration-reference-model.md` — config entities, precedence, future UI mapping
- **Planned in-tree:** `docs/operations/governance-reason-code-catalog.md` — reason-code maintenance contract (see `traceability-matrix.md`)

## Local workspace templates (copy into `.local/`)

- `docs/templates/local-workspace/pages.json`
- `docs/templates/local-workspace/implementation-control-center.html`
- Run `python scripts/dev/migrate_local_workspace_layout.py` after upgrades

## Historical/archived references

- `docs/archive/operations/local-ui-readiness-smoke.md` (historical)
- `docs/plans/docs-archive-index.md` (full archive mapping)
