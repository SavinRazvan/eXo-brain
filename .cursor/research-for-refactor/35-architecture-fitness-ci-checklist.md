# Architecture Fitness CI Checklist

## Goal
Provide a copy-ready CI checklist that prevents monolithic drift and enforces modular, provider-neutral, policy-governed architecture over time.

## When to Run
- On every PR touching `src/core`, `src/runtime`, `src/tools`, `src/policies`, `src/observability`, `src/persistence`, `src/integration`, or `configs/`.
- On release candidate pipelines before promotion.

## Hard-Block Checks (`P0`)

## 1) Layer Boundary Rules
- [ ] `core/` does not import provider SDK packages directly.
- [ ] `core/` does not import transport/framework controllers (`FastAPI`, `CLI`, web handlers).
- [ ] `integration/` does not contain orchestration or policy decision logic.
- [ ] `tools/` side-effect paths route through policy middleware.
- [ ] `runtime/` adapter implementations do not bypass contract envelopes.

## 2) Provider-Neutral Rules
- [ ] No provider-name branching in orchestration core (no `if provider == ...` in `core/`).
- [ ] Execution mode chosen by capability + policy (`provider_native` vs `deterministic`).
- [ ] Adapter additions do not require orchestrator internals rewrite.
- [ ] Runtime adapter contract methods are fully implemented:
  - `start_session(session_id, metadata=None)`
  - `run_turn(...)`
  - `submit_tool_results(...)`
  - `get_capabilities()`
  - `healthcheck()`

## 3) Anti-Monolith Structural Rules
- [ ] No new file exceeds agreed complexity threshold without ADR/exception.
- [ ] No module mixes provider adapter + orchestration + policy ownership.
- [ ] Cross-layer imports match approved direction:
  - `integration -> core`
  - `core -> runtime/tools/policies/persistence/observability`
  - no reverse ownership imports into `core`.
- [ ] New feature delivered via extension points (adapter/plugin/decorator), not core patching by default.

## 4) Observability and Security Invariants
- [ ] Correlation IDs propagated (`job_id`, `task_id`, `session_id`, `run_id`, `agent_id`, `call_id`, `provider_id`).
- [ ] Policy decisions include auditable reason codes.
- [ ] Side-effecting tool calls emit mode + decision + attempt + duration fields.
- [ ] Secret scanning, redaction checks, and dependency security checks pass.

## Soft-Block Checks (`P1`)
- [ ] Architecture fitness trend stable (no rising boundary violations over last N PRs).
- [ ] Plugin/adapter conformance suite passes with no skipped tests.
- [ ] Workflow parity check passes for baseline + candidate adapter.
- [ ] Fallback/rollback simulation succeeds for degraded provider scenario.

## Evidence Artifacts (Attach to PR/RC)
- Architecture dependency report (import-boundary validation output).
- Forbidden import scan report.
- Adapter conformance summary.
- Mode-selection decision trace sample.
- Security scan summary (secrets + dependencies).

## Suggested CI Step Order
1. Static architecture checks (imports, layering, forbidden dependencies).
2. Contract tests (runtime adapters, policy, tool envelopes).
3. Integration checks (deterministic side-effect path + observability fields).
4. Security scans.
5. Evidence bundle upload.

## Failure Policy
- Any `P0` failure: block merge/deploy.
- `P1` degradation: require explicit risk acceptance and remediation plan.

## Example CI Task Map
- `architecture_lint`
- `forbidden_import_scan`
- `contract_tests`
- `integration_architecture_fitness`
- `security_scan`
- `evidence_bundle_publish`

## Related Docs
- `09-definition-of-done-and-quality-gates.md`
- `15-enterprise-quality-gates.md`
- `16-enterprise-testing-strategy.md`
- `17-enterprise-cicd-governance.md`
- `23-pr-release-evidence-templates.md`
- `32-adapter-conformance-checklist.md`
- `34-provider-registry-and-settings-schema.md`
