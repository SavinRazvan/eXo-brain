# Research For Refactor

This folder contains architecture research and planning artifacts for building a new repository focused on a dynamic multi-layer agent system with OpenAI Agents SDK.

## What Is Included
- `01-flexiai-reusable-assets.md`: what to reuse from current `flexiai` codebase.
- `02-target-architecture.md`: proposed layered structure and interfaces.
- `03-tool-calling-decision.md`: decision framework between FlexiAI tool calling and OpenAI-native tool calling.
- `04-phased-migration-plan.md`: concrete migration plan and validation gates.
- `05-background-multi-agent-runtime.md`: dynamic background runtime model, scaling, scheduling, plugin lifecycle, and reliability requirements.
- `06-mvp-build-sequence.md`: practical 2-week, file-by-file MVP implementation sequence.
- `07-agent-orchestration-plan.md`: execution workflow for architecture/planning agents and handoff contracts.
- `08-module-requirements-matrix.md`: explicit requirements per module and global NFRs.
- `09-definition-of-done-and-quality-gates.md`: release-ready quality gates for architecture and implementation phases.
- `10-provider-capability-matrix.md`: capability model for OpenAI + open-source LLM providers and runtime adapter selection rules.
- `11-port-matrix.md`: file-level `reuse`/`adapt`/`do_not_reuse` mapping from `flexiai-toolsmith` into destination modules for the new repo.
- `12-bootstrap-checklist.md`: day-0 to first-vertical-slice execution checklist for bootstrapping the new repository.
- `13-project-structure-blueprint.md`: canonical repository structure and high-level mermaid architecture flow.
- `14-enterprise-readiness-modules.md`: additional enterprise modules (`P0`/`P1`/`P2`) for identity, tenancy, compliance, resilience, finops, and governance.
- `15-enterprise-quality-gates.md`: measurable enterprise release gates (SLO/KPI/evidence pack/go-no-go) for production readiness.
- `16-enterprise-testing-strategy.md`: enterprise testing architecture covering contracts, replay, chaos, performance, canaries, and rollout validation.
- `17-enterprise-cicd-governance.md`: enterprise CI/CD governance blueprint for signed artifacts, progressive rollout, rollback, and auditable release controls.
- `18-enterprise-operational-runbooks.md`: essential incident response and recovery runbooks for SEV-1, rollback, failover, saturation, checkpoint restore, and security compromise.
- `19-enterprise-security-baseline-controls.md`: essential security controls matrix (`P0`/`P1`/`P2`) with verification cadence and minimum release evidence.
- `20-implementation-coding-standards.md`: execution-phase coding and module-boundary standards for implementation consistency.
- `21-execution-workflow-and-handoffs.md`: standard execution flow and mandatory handoff contract between architecture/tooling/migration tracks.
- `22-interface-contract-template.md`: reusable interface contract template for adapters, tools, policies, and stores.
- `23-pr-release-evidence-templates.md`: PR and release-candidate evidence templates aligned with quality/security gates.
- `24-repo-bootstrap-scaffold.md`: minimal repo bootstrap scaffold and validation gates for day-0 setup.
- `25-technology-stack-decisions.md`: redacted technology stack decision baseline for cloud-agnostic hybrid deployment.
- `26-deployment-profiles-matrix.md`: managed-cloud vs self-hosted profile matrix with contract parity and validation requirements.
- `27-reference-tech-stack-lock-v1.md`: locked V1 reference stack with deferred items, version policy, and change-control rules.
- `28-persistence-module-and-hybrid-db-strategy.md`: first-class persistence module design and hybrid local/remote DB adapter strategy.
- `29-versioning-and-release-roadmap.md`: semantic versioning strategy and phased roadmap (`v1` foundation -> `v1.x` hardening -> `v2` expansion).
- `30-project-naming-and-conventions.md`: canonical naming conventions for brand/repo/package/symbols, including ready-to-paste sections for README and architecture docs.

## Current Direction
- Use proven orchestration and deterministic tool execution patterns from `flexiai`.
- Keep architecture provider-agnostic through adapter boundaries.
- Decide tool-calling runtime per layer based on determinism, observability, and operational risk.
- Support plug-in/plug-out provider runtime adapters (OpenAI-native, OpenAI-compatible, custom adapters for OSS models).
- Keep the framework embeddable as a small module/SDK that can plug into any host app/interface.

## Source Reference
- Upstream repository: https://github.com/SavinRazvan/flexiai-toolsmith
- Snapshot commit used in these notes: `3f8b0c7a0996117dc95f0a8b93678dae44a5b0d6`
