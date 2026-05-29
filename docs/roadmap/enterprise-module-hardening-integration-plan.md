<!--
File: enterprise-module-hardening-integration-plan.md
Path: docs/roadmap/enterprise-module-hardening-integration-plan.md
Role: Phased module hardening program for src/* with gates and integration verification.
Used By:
 - docs/roadmap/README.md
 - Platform maintainers, implementer agents
Depends On:
 - docs/architecture/workspace-architecture.md
 - docs/strategy/traceability-matrix.md
Notes:
 - Preserve control-plane vs customer-bridge vs provider-adapter vocabulary when updating related docs.
-->

# Enterprise Module Hardening + Integration Plan

## Document Metadata
- Status: Active (program tracker — not a “everything is TODO” map of product readiness)
- Owner: Savin I. Razvan
- Scope: `src/*`, `tests/modules/*`, CI architecture fitness workflows
- Last reviewed: 2026-05-29
- Related:
  - [docs/roadmap/README.md](README.md)
  - [docs/architecture/mvp.md](../architecture/mvp.md)
  - [docs/architecture/governed-execution-pipeline.md](../architecture/governed-execution-pipeline.md)
  - [docs/modules/README.md](../modules/README.md)
  - [docs/runtime_contracts.md](../runtime_contracts.md)
  - [docs/mcp_integration.md](../mcp_integration.md)
  - [docs/operations/adapter-installation.md](../operations/adapter-installation.md)
  - `AGENTS.md`
  - [module-hardening-slice-checklist.md](module-hardening-slice-checklist.md)
  - [governed-execution-positioning.md](../strategy/governed-execution-positioning.md)
  - [control-plane-product-alignment-plan.md](../plans/control-plane-product-alignment-plan.md)

## 1) Goal
Harden each module with deterministic checks, structured logs, explicit error handlers, and integration verification while preserving provider-neutral architecture boundaries and the **control plane** as the non-bypassable enforcement layer (see `docs/strategy/governed-execution-positioning.md`).

## 2) Program Success Criteria
- All module boundaries enforce input/output validation.
- All state-changing/high-impact operations remain deterministic-first and policy-gated.
- Correlation IDs propagate across core, runtime, policies, tools, and MCP execution paths.
- Error envelopes are typed, consistent, and test-covered.
- Tests and merge gates pass (canonical order: `scripts/pr/prepare.py` `GATES`):
  - `python scripts/pr/check_testing_artifacts.py`
  - `pytest -q`
  - `python scripts/architecture/validate_layers.py`
  - `python scripts/architecture/scan_forbidden_imports.py`
- When governance/workflows/policy docs change: `python scripts/architecture/check_governance_consistency.py`
- CI workflow targets and test paths remain aligned with `tests/modules/*` (see `.github/workflows/`).

## 3) Guardrails (Must Not Regress)
- No provider SDK imports outside runtime adapter modules (`src/runtime/*` and published packages loaded via `src/runtime/adapter_factory.py` — see [adapter-installation.md](../operations/adapter-installation.md)).
- No provider-name branching in orchestration core.
- No bypass for deterministic policy-governed state-changing/high-impact paths.
- No cross-layer shortcuts that skip policy middleware.
- No silent error swallowing in runtime/tool execution paths.

## 4) Execution Model
Use small PR slices, one module group per slice.

Each slice follows:
1. Confirm contracts and acceptance gates.
2. Add/strengthen checks and validation.
3. Add/normalize structured logs.
4. Add explicit error classes/handlers and deterministic envelopes.
5. Add tests (happy path, failure path, retry/fallback path when relevant).
6. Run full gates and update evidence artifacts.
7. Merge and clean branch before next slice.

## 5) Phase Plan (Recommended Order)

### Phase 0 - Foundation Baseline
**Modules:** `src/schemas`, `src/observability`, `src/policies`

**Objective**
- Standardize shared validation + logging + decision contracts used by all other modules.

**Scope**
- Normalize error envelope fields in `src/schemas/*`.
- Normalize log context fields and redaction expectations in `src/observability/*`.
- Normalize policy decision metadata and reason-code consistency in `src/policies/*`.

**Verification**
- `pytest -q tests/modules/schemas tests/modules/observability tests/modules/policies`
- Full gates (pytest + architecture checks)

**Exit Criteria**
- Shared contracts stable and consumed by downstream modules without ambiguity.

### Phase 1 - Tools + Runtime Safety Core
**Modules:** `src/tools`, `src/runtime`, packaged adapters (PyPI via SavinRazvan/eXo_adapters)

**Objective**
- Ensure tool execution and runtime adapters fail deterministically and observably.

**Scope**
- Validate tool descriptor and call payloads.
- Ensure runtime adapter exceptions map to stable internal event/error contracts.
- Ensure fallback behavior is explicit when provider-native paths fail safety constraints.
- Conformance for published adapters: `tests/packages/test_openai_adapter_conformance.py`, `tests/modules/runtime/test_packaged_adapter_e2e.py`.

**Verification**
- `pytest -q tests/modules/tools tests/modules/policies tests/modules/runtime tests/modules/observability/test_executor.py`
- `pytest -q tests/modules/core/test_orchestrator_turn.py tests/modules/core/test_multi_adapter_workflow_parity.py`
- `pytest -q tests/packages/` (adapter conformance when touching packaged refs)
- Full gates

**Exit Criteria**
- Consistent runtime/tool error behavior across all adapters.

### Phase 2 - MCP Boundary Hardening
**Modules:** `src/mcp`

**Objective**
- Make MCP tool/server failures deterministic, typed, and auditable.

**Scope**
- Strengthen server/tool resolution checks.
- Ensure circuit breaker and DLQ paths emit explicit reason codes and context.
- Add clear observability events for trust-tier and health-state decisions.

**Verification**
- `pytest -q tests/modules/mcp`
- Full gates

**Exit Criteria**
- MCP failures are safe, classified, and debuggable.

### Phase 3 - Core Orchestration + Integration
**Modules:** `src/core`, `src/integration`

**Objective**
- Harden orchestration lifecycle transitions and boundary handling.

**Scope**
- Validate session/context/event boundaries.
- Harden cancellation/resume/retry and background task transitions.
- Ensure host adapter propagation of correlation + identity + tenant context remains explicit.

**Verification**
- `pytest -q tests/modules/core`
- Full gates

**Exit Criteria**
- Orchestration paths are validated, recoverable, and fully traceable.

### Phase 4 - Persistence + Resilience
**Modules:** `src/persistence`, `src/resilience`

**Objective**
- Ensure storage and recovery paths have explicit invariants and failure controls.

**Scope**
- Validate persistence contract invariants.
- Ensure retry, breaker, and DLQ semantics are deterministic and observable.
- Add error handling around adapter/store failures with clear retryability boundaries.

**Verification**
- `pytest -q tests/modules/persistence tests/modules/resilience`
- Full gates

**Exit Criteria**
- Durable state and failure recovery behaviors are predictable and tested.

### Phase 5 - Security Domain Hardening
**Modules:** `src/identity`, `src/access_control`, `src/tenancy`, `src/secrets`

**Objective**
- Lock down identity/authorization/tenancy/secrets controls and observability.

**Scope**
- Validate identity and role context requirements.
- Enforce access and escalation decision consistency.
- Enforce tenancy quotas/overlays and cross-tenant isolation checks.
- Confirm secrets redaction and safe provider behavior under failures.

**Verification**
- `pytest -q tests/modules/access_control tests/modules/secrets tests/modules/persistence/test_cross_tenant_isolation.py`
- Full gates

**Exit Criteria**
- Security-critical paths are explicit, policy-checked, and auditable.

### Phase 6 - Audit + Compliance + Release Governance
**Modules:** `src/audit`, `src/compliance`, `scripts/release/*`, release docs

**Objective**
- Ensure evidence generation and release decisions are complete and deterministic.

**Scope**
- Validate audit chain integrity behavior.
- Ensure evidence bundles include expected quality/security/runtime artifacts.
- Harden release helper script error handling and output contracts.

**Verification**
- `pytest -q tests/modules/audit tests/modules/pr_workflow tests/modules/architecture_scripts tests/modules/release_scripts tests/modules/perf_scripts`
- `pytest -q tests/modules/observability/test_release_guardrails.py`
- Full gates

**Exit Criteria**
- Governance and release artifacts are reliable and complete.

### Phase 7 - API + Cross-Module Stabilization
**Modules:** `src/api`, `src/modules/*`, cross-cutting + CI

**Objective**
- Final confidence pass across northbound API, composition root (`AppModules`), architecture CI, and operator docs.

**Scope**
- Confirm routers and `/tenants` mounts match [customer-api-integration-guide.md](../api/customer-api-integration-guide.md).
- Confirm workflows reference current paths (`tests/modules/*`, notebooks CI when applicable).
- Run repeated full-gate passes to detect flakiness.
- Re-check `docs/modules/*`, API docs, and runbooks for changed behavior.

**Verification**
- 2 consecutive green full-gate runs
- CI checks green on PR and post-merge main

**Exit Criteria**
- Stable merge-ready baseline with no known blocking gaps.

## 6) Per-Slice Acceptance Gates
For each PR slice, all must pass:
- Module-level tests for touched areas
- `scripts/pr/prepare.py` gates (or equivalent manual run): testing-artifacts check, `pytest -q`, `validate_layers.py`, `scan_forbidden_imports.py`
- Architecture-impacting PRs: alignment artifacts per [alignment-audit-schema.md](alignment-audit-schema.md) when required by workflow
- Updated `.local/workflow-artifacts/pr/review.md`, `prep.md`, and `merge.md` through the maintainer PR workflow
- Rollback/fallback notes captured in PR body

## 7) Rollback Strategy
- Keep each slice isolated to one module group + related tests.
- Revert by commit if regressions appear.
- Use configuration flags for temporary safe fallback only when needed.
- Follow with patch-forward fix in next focused slice.

## 8) Risks and Mitigations
- **Cross-layer coupling risk:** enforce contracts in `src/schemas` and reject shortcut imports.
- **CI drift risk:** include workflow path checks whenever tests move.
- **Silent failures risk:** require explicit reason-code-bearing error envelopes.
- **Performance drift risk:** keep targeted baseline checks in core/runtime paths.

## 9) Tracking Table

Update this table when a **program slice** branch merges. Baseline platform capabilities (governed API, adapters on PyPI, notebooks) may exist before a row moves off `planned`.

| Slice | Module Group | Branch Name | Status | Tests | Arch Checks | PR |
|---|---|---|---|---|---|---|
| 0 | schemas/observability/policies | `feature/hardening-foundation` | planned | pending | pending | TBD |
| 1 | tools/runtime (+ packaged adapters) | `feature/hardening-tools-runtime` | planned | pending | pending | TBD |
| 2 | mcp | `feature/hardening-mcp-boundary` | planned | pending | pending | TBD |
| 3 | core/integration | `feature/hardening-core-integration` | planned | pending | pending | TBD |
| 4 | persistence/resilience | `feature/hardening-persistence-resilience` | planned | pending | pending | TBD |
| 5 | identity/access/tenancy/secrets | `feature/hardening-security-domain` | planned | pending | pending | TBD |
| 6 | audit/compliance/release | `feature/hardening-audit-compliance` | planned | pending | pending | TBD |
| 7 | api/modules + e2e stabilization | `feature/hardening-e2e-stabilization` | planned | pending | pending | TBD |

## 10) Final Definition of Done
- All slices completed and merged through PR workflow.
- All architecture and quality gates green.
- No unresolved P0/P1 safety or architecture findings.
- Docs, runbooks, and release templates aligned with implementation behavior.
