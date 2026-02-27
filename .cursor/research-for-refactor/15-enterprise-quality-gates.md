# Enterprise Quality Gates

## Goal
Define measurable enterprise release gates (SLOs, security, compliance, governance, and operations) so production readiness is objective and auditable.

## Scope
This document extends:
- `09-definition-of-done-and-quality-gates.md` (project-level gates)
- `14-enterprise-readiness-modules.md` (module-level enterprise capabilities)

Use this file as the final pass/fail checklist before onboarding production tenants.

## Gate Model
- `P0` (hard block): must pass before production go-live.
- `P1` (scale readiness): must pass before multi-tenant scale expansion.
- `P2` (optimization): improves maturity and efficiency; can follow initial launch if risk accepted.

## Release Gate Matrix

| Gate Area | Priority | Metric / Evidence | Target | Verification Method | Fail Action |
|---|---|---|---|---|---|
| Tenant Isolation | P0 | Cross-tenant read/write attempts blocked | 100% blocked in tests | Isolation integration suite + chaos scenarios | Block release |
| AuthN/AuthZ | P0 | Unauthorized privileged actions denied | 100% denied | Policy tests + audit replay | Block release |
| Secret Hygiene | P0 | Secrets leaked in logs/artifacts | 0 incidents in CI scans | Secret scanner + log redaction tests | Block release |
| Audit Integrity | P0 | Tamper-evident audit chain validation | 100% valid chain segments | Audit verifier job | Block release |
| Critical Reliability | P0 | Workflow success rate (critical class) | >= 99.5% rolling 7d | SLO dashboard + synthetic canaries | Freeze rollout / incident response |
| Recovery Objective | P0 | RTO for orchestrator/service restart | <= 15 min | Disaster-recovery exercise | Block release |
| Data Protection | P1 | Sensitive field redaction coverage | 100% required fields redacted | Data classification tests + export checks | Halt affected feature |
| Budget Governance | P1 | Cost attribution completeness | >= 99% jobs attributed | FinOps pipeline validation | Disable untracked workloads |
| Provider Governance | P1 | Model promotion without approved eval | 0 promotions bypassing gate | CI governance checks | Block model promotion |
| Performance | P1 | P95 end-to-end latency (interactive tier) | <= 3.0s (target profile) | Load test + tracing | Capacity tuning / release hold |
| Incident Operations | P1 | MTTD / MTTR for Sev-1 | MTTD <= 5m, MTTR <= 30m | Game-day drills + incident logs | SRE remediation plan required |
| Capacity Elasticity | P2 | Worker autoscale convergence | <= 2 min to recover queue backlog | Load burst testing | Tune autoscaler policies |
| Change Safety | P2 | Change failure rate | <= 10% | Deployment analytics | Tighten rollout strategy |
| Availability | P2 | Service availability | >= 99.9% monthly | Uptime SLI dashboards | Capacity + resilience review |

## SLO Bundle (Minimum Enterprise Baseline)

Define and publish these SLOs per environment (`stage`, `prod`):
- Success Rate SLO: percentage of workflows completed without policy/runtime failure.
- Latency SLO: `P50`, `P95`, `P99` by workflow class (`interactive`, `background`, `batch`).
- Freshness SLO: max delay for event/timeline ingestion into observability store.
- Recovery SLO: restore checkpointed background workloads after orchestrator outage.
- Security SLO: mean time to revoke compromised credentials and enforce policy update.

## Quality Gate Execution Pipeline
1. **Static gates**: schema checks, policy linting, secret scanning, dependency/license checks.
2. **Contract gates**: adapter/tool/plugin contract tests and compatibility matrix checks.
3. **Scenario gates**: deterministic workflow replay and high-risk action simulations.
4. **Resilience gates**: retry/circuit-breaker/DLQ and recovery drills.
5. **Observability gates**: verify correlation IDs, timeline completeness, and audit lineage.
6. **Governance gates**: model/provider promotion checks tied to evaluation evidence.
7. **Operational gates**: SLO burn-rate checks, alert routing validation, runbook completeness.

## Evidence Requirements (Audit Pack)

Every release candidate must generate an evidence bundle:
- test reports (unit/integration/contract/resilience)
- SLO snapshot export (last 7d and 30d)
- audit-chain integrity report
- policy decision logs for high-risk workflows
- model/provider evaluation report for promoted configurations
- incident drill report (latest run)

Store bundles in immutable, retention-managed storage with release tag linkage.

## Go/No-Go Checklist

Release is **GO** only when all statements are true:
- [ ] all `P0` gates pass with current evidence
- [ ] no open Sev-1 / Sev-2 incidents related to core runtime or policy engine
- [ ] no unresolved audit-integrity or tenant-isolation findings
- [ ] SLO burn rate is below alert thresholds
- [ ] rollback plan is tested and approved

Release is **NO-GO** if any `P0` gate fails or evidence is missing.

## Ownership and RACI
- Architecture owner: gate definitions and threshold updates.
- Security owner: auth, secret hygiene, compliance, audit integrity.
- Runtime owner: reliability, recovery, performance, capacity.
- SRE owner: SLO monitoring, alerting, incident response readiness.
- Product/Program owner: final go/no-go approval using evidence pack.

## Suggested File Hooks In New Repo
- `src/observability/slo_registry.py`
- `src/observability/gate_evaluator.py`
- `src/compliance/evidence_bundle.py`
- `src/policies/release_guardrails.py`
- `tests/quality_gates/`

## Related Docs
- `09-definition-of-done-and-quality-gates.md`
- `10-provider-capability-matrix.md`
- `12-bootstrap-checklist.md`
- `14-enterprise-readiness-modules.md`
- `16-enterprise-testing-strategy.md`
