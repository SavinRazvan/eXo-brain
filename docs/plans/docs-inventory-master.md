<!--
File: docs-inventory-master.md
Path: docs/plans/docs-inventory-master.md
Role: Master inventory of repository documentation with lifecycle status and canonical pointers.
Used By:
 - docs/plans/docs-authority-map.md
 - docs/plans/docs-archive-index.md
Depends On:
 - docs/README.md
 - docs/plans/README.md
Notes:
 - Inventory should be updated whenever docs status changes.
-->

# Documentation Inventory (Master)

## Active Canonical

| Path | Role |
|---|---|
| `README.md` | Project entrypoint and developer quick-start |
| `docs/README.md` | Top-level documentation index (reading spine, module/API/plan pointers) |
| `docs/modules/README.md` | P0 module doc index; map to `src/` trees, `src/modules/` slices, and tests |
| `docs/modules/core.md` | Orchestrator, scheduler, session, workflow — provider-neutral core |
| `docs/modules/runtime.md` | RuntimeAdapter, adapter_factory, tenant runtime, packaged adapters |
| `docs/modules/tools.md` | Deterministic executor, sandbox, BYOC, tool HTTP governance |
| `docs/modules/policies.md` | Ingress gates, policy middleware, entitlements, templates |
| `docs/modules/tenancy.md` | Policy overlay, quotas, rate limits, tenant isolation |
| `docs/modules/api.md` | FastAPI transport, `AppModules` composition root, `/tenants` mounts |
| `docs/api/README.md` | API folder index, `/tenants` path convention, reading order |
| `docs/api/customer-api-integration-guide.md` | Tier-aware API contract documentation for customer onboarding (chat/agents/workflow + governance ingress); endpoint paths aligned with `src/api/app.py` mounts |
| `docs/api/governance-preview-and-testing.md` | **Planned (file not in repo yet)** — self-serve governance testing patterns, feedback loop, simulation/dry-run APIs (`traceability-matrix.md`) |
| `docs/strategy/customer-self-serve-governance-journey.md` | Canonical customer self-serve governance product contract and implementer checklist |
| `docs/strategy/foundation-tier-adoption-checklist.md` | Foundation-tier API adoption steps with Pro/Enterprise deltas |
| `docs/plans/governance-configuration-reference-model.md` | Unified configuration entity model, dependency order, precedence, thin-UI mapping |
| `docs/operations/governance-reason-code-catalog.md` | **Planned (file not in repo yet)** — reason-code ownership and discovery process (`traceability-matrix.md`) |
| `docs/architecture/beginner-workflow.md` | Beginner-friendly plain-language walkthrough of the platform workflow |
| `docs/architecture/mvp.md` | Layer architecture and design intent (canonical) |
| `docs/architecture_mvp.md` | Redirect stub → `docs/architecture/mvp.md` (last reviewed 2026-05-29) |
| `docs/architecture/workspace-architecture.md` | Workspace doctrine (adapters, policy, enterprise controls) |
| `docs/architecture/ARCHITECTURE.md` | Consolidated map: planes, Option C/strategy vocabulary, mermaid A–C, layers, modules, plans × concerns, maintainer checklist §14 |
| `docs/architecture/README.md` | Architecture folder index and recommended reading order |
| `docs/architecture/governed-execution-pipeline.md` | Canonical control-plane ordering: entitlements, ingress, orchestrator, tool policy, deterministic execution vs provider-native; direct-`Orchestrator` bypass warning; Hands-on proof ↔ `tutorial_08` |
| `docs/strategy/README.md` | Strategy package index, reading order, shipped vs planned snapshot |
| `docs/strategy/goal.md` | Product north star and platform boundary |
| `docs/strategy/core.md` | Core invariants and governance model |
| `docs/strategy/adapter-strategy.md` | Adapter ecosystem, lanes, certification |
| `docs/strategy/adapter-compatibility-matrix.md` | Published package versions (0.1.1), semver, M0/M1 status |
| `docs/strategy/monetization-strategy.md` | Monetization and tier value capture |
| `docs/strategy/governed-execution-positioning.md` | Product boundary, ICP, monetization posture, and messaging guardrails for governed execution |
| `docs/strategy/entitlement-matrix.md` | Feature-to-tier enforcement matrix |
| `docs/strategy/compliance-profile-matrix.md` | Compliance waves and control mapping |
| `docs/strategy/deployment-models.md` | Deployment packaging and support boundaries |
| `docs/strategy/interface-strategy.md` | API-first interface strategy |
| `docs/strategy/traceability-matrix.md` | Strategy ↔ code ↔ test traceability and gaps |
| `docs/strategy/next-directions.md` | Tiered next implementation directions |
| `docs/strategy/execution-board-12-gaps.md` | Execution board for 12 priority gaps |
| `docs/operations/workflow-complete.md` | Maintainer workflow checklist (durable) |
| `docs/operations/agent-workflow-procedures.md` | Audit/PR dedup procedures; **§3b** git commit vs PR artifact provenance sync list |
| `docs/operations/local-workspace-layout.md` | Gitignored `.local/` layout; git trailers vs `.local/workflow-artifacts/pr/*` |
| `docs/operations/documentation-maintenance-checklist.md` | Maintainer checklist when architecture, API, tenancy, or workflow docs change |
| `docs/operations/logging-and-errors.md` | Logging rollout plan |
| `docs/governance/README.md` | Governance folder index (charter, source owners, drift prevention) |
| `docs/governance/folder-charter.md` | `docs/` vs `.local/` charter |
| `docs/governance/path-migration-map.md` | Old → new path map |
| `docs/governance/workflow-source-owners.md` | Script-first ownership map |
| `docs/governance/drift-prevention.md` | Lightweight drift process |
| `docs/governance/rollout-phases.md` | IA rollout phase notes |
| `docs/governance/rules-overlap-matrix.md` | Cursor rules inventory / Track D |
| `docs/roadmap/README.md` | Roadmap index: alignment audits + module hardening program |
| `docs/roadmap/alignment-audit-schema.md` | Advisory alignment finding schema (P0/P1/P2, categories, precedence) |
| `docs/roadmap/alignment-audit-report-template.md` | Starter for `.local/workflow-artifacts/alignment/alignment-audit.md` |
| `docs/roadmap/alignment-todos-template.md` | Starter for `.local/workflow-artifacts/alignment/alignment-todos.md` |
| `docs/roadmap/enterprise-module-hardening-integration-plan.md` | Phased module hardening program and slice tracking table |
| `docs/roadmap/module-hardening-slice-checklist.md` | Per-PR hardening checklist (gates, PR artifacts, docs) |
| `docs/runtime_contracts.md` | RuntimeAdapter ABC (exo-brain-core-contracts), mode selection, northbound/southbound; links ADR submit_tool_results |
| `docs/mcp_integration.md` | MCP registry/trust/health/policy-gated adapter; integration status vs default API path |
| `docs/plugin_lifecycle.md` | Tool + agent plugin managers (load/unload/reload/compatibility) |
| `docs/workflow_loading.md` | WorkflowLoader JSON/YAML registry; error codes; orchestration wiring status |
| `docs/plans/tenant-tool-execution-architecture.md` | Canonical current implementation status and execution architecture |
| `docs/plans/option-c-contract-freeze.md` | Option C contract freeze source |
| `docs/plans/option-c-worker-isolation-contract.md` | Option C worker isolation contract |
| `docs/plans/option-c-performance-gates.md` | Option C performance/SLO gate definitions |
| `docs/operations/release-candidate-signoff-checklist.md` | Canonical release signoff process |
| `docs/releases/RELEASE_TEMPLATE.md` | Release / rollout note template (RC vs git trailer disclosure) |
| `configs/release/README.md` | Release gate config bundle index (`configs/release/*.yaml` + JSON); git vs RC evidence |
| `scripts/pr/README.md` | PR workflow scripts hub (artifact paths vs **commit-trailer-format.mdc**) |
| `docs/operations/byoc-failure-injection-playbook.md` | BYOC failure drills |
| `docs/operations/byoc-artifact-integrity-dashboard.md` | BYOC integrity operations guidance |
| `docs/plans/short-long-term-execution-plan.md` | Short vs long execution horizons; companion to `next-directions.md` Tier emphasis |
| `docs/plans/short-long-term-execution-plan.plan.md` | Implementer companion (W1–W4+S4, checklists, slice boilerplate) |
| `docs/plans/notebook-standards.md` | Notebook categories, builders, CI, ownership map |
| `notebooks/README.md` | Notebook index (14), prerequisites, per-notebook breakdown |
| `notebooks/EVALUATOR_GUIDE.md` | Time-boxed evaluator paths (15 min / 90 min / security / smoke) |
| `docs/decisions/README.md` | Architecture decision index (ADR-style) |
| `docs/decisions/submit-tool-results-orchestrator-only.md` | OpenAI adapter `submit_tool_results` / continuation decision |
| `docs/handoffs/README.md` | Handoff index (completed missions → canonical ops docs) |
| `docs/handoffs/exo_adapters_pypi_handoff.md` | Adapter extraction **completion status** (not a live mission playbook) |
| `docs/operations/adapter-installation.md` | Operator install of published adapter wheels |
| `docs/operations/adapter-repos-and-pypi.md` | GitHub/PyPI layout (eXo-brain vs eXo_adapters) |
| `docs/plans/adapter-packages-extraction-handoff.md` | Package inventory + §9 cleanup checklist |

## Planned / Working

| Path | Role |
|---|---|
| `docs/plans/docs-inventory-master.md` | Lifecycle inventory and classification table |
| `docs/plans/docs-authority-map.md` | Authority and precedence map for docs |
| `docs/plans/docs-archive-index.md` | Archive index and replacement mapping |
| `docs/plans/control-plane-product-alignment-plan.md` | Control plane vs adapter vs customer bridge narrative |
| `docs/plans/adapter-packages-extraction-handoff.md` | Adapter packages extraction checklist (separate repos) |

## Archived / Historical

| Path | Replacement |
|---|---|
| `docs/archive/plans/backlog-reconciliation-v2-execution-board.md` | `docs/plans/tenant-tool-execution-architecture.md` |
| `docs/archive/plans/backlog-reconciliation-v3-execution-board.md` | `docs/plans/tenant-tool-execution-architecture.md` |
| `docs/archive/plans/backlog-reconciliation-v3-execution-plan.md` | `docs/plans/tenant-tool-execution-architecture.md` |
| `docs/archive/plans/backlog-reconciliation-v4-execution-board.md` | `docs/plans/tenant-tool-execution-architecture.md` |
| `docs/archive/plans/p2-expansion-roadmap.md` | `docs/plans/tenant-tool-execution-architecture.md` |
| `docs/archive/operations/local-ui-readiness-smoke.md` | `docs/operations/release-candidate-signoff-checklist.md` |
| `docs/archive/results/audit_alignment_results.md` | `.local/workflow-artifacts/alignment/alignment-audit.md` |
| `docs/archive/results/audit_alignment_action_plan.md` | `.local/workflow-artifacts/alignment/alignment-todos.md` |
| `docs/archive/plans/api-platform.md` | `docs/plans/tenant-tool-execution-architecture.md`, `docs/architecture/ARCHITECTURE.md` |
| `docs/archive/plans/platform-extensions.md` | `docs/plans/tenant-tool-execution-architecture.md`, `docs/plans/option-c-contract-freeze.md`, `docs/plans/option-c-worker-isolation-contract.md`, `docs/plans/option-c-performance-gates.md` |
| `docs/archive/plans/archive-agents-research.md` | N/A — use `.cursor/agents`, `.cursor/skills`, `.agents/skills` for current automation assets |
| `docs/archive/plans/docs-inventory.md` | `docs/plans/docs-inventory-master.md` |
| `docs/archive/plans/notebooks-inventory.md` | `notebooks/README.md`, `docs/plans/notebook-standards.md` |
| `docs/archive/plans/docs-governance-baseline-map.md` | `docs/plans/docs-authority-map.md`, `docs/plans/docs-archive-index.md` |
| `docs/archive/plans/northbound-v1-gateway.md` | `docs/api/customer-api-integration-guide.md` (§4.0), `docs/plans/tenant-tool-execution-architecture.md`, `src/api/routers/openai_gateway.py` |
| `docs/archive/plans/enterprise-audit-remediation-plan.md` | `docs/strategy/traceability-matrix.md`, `docs/plans/tenant-tool-execution-architecture.md`, `.github/workflows/architecture-fitness.yml` |
| `docs/archive/plans/documentation-cleanup-master-plan.md` | `docs/plans/docs-inventory-master.md`, `docs/plans/docs-authority-map.md`, `docs/governance/drift-prevention.md` |
| `docs/archive/plans/docs-and-notebooks-cleanup-plan.md` | `docs/plans/notebook-standards.md`, `notebooks/README.md`, `docs/plans/docs-inventory-master.md` |
| `docs/archive/plans/post-monolith-execution-roadmap.md` | `docs/strategy/next-directions.md`, `docs/plans/short-long-term-execution-plan.md`, `docs/strategy/traceability-matrix.md`, `docs/plans/tenant-tool-execution-architecture.md` |
| `docs/archive/plans/adapter-ecosystem-gateway-hygiene-plan.md` | `docs/strategy/adapter-strategy.md`, `docs/strategy/next-directions.md`, `docs/plans/adapter-packages-extraction-handoff.md`, `docs/plans/short-long-term-execution-plan.md` |
| `docs/archive/plans/adapter-ecosystem-gateway-hygiene-todos.md` | Same as hygiene plan (checkbox snapshot) |
| `docs/archive/plans/control-plane-product-alignment-baseline-slice-closed.md` | `docs/plans/control-plane-product-alignment-plan.md` (ongoing L1–L4) |

## Notes

- `docs/archive/*` contains non-authoritative historical documents with replacement pointers.
- `.local/*` artifacts are execution evidence snapshots and not long-lived canonical docs.
