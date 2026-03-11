# Option C Performance Gates

## Status

- Date: 2026-03-11
- Scope: Slices D + E (`runbook-sliceD`, `runbook-sliceE`)

## Locked SLO Targets (baseline)

These are initial rollout gates and may be tightened after production profiling.

| Metric | Target | Gate type |
|---|---:|---|
| Turn p50 latency | <= 800 ms | soft warning |
| Turn p95 latency | <= 2500 ms | hard block |
| Turn error rate | <= 1.0% | hard block |
| Turn timeout rate | <= 0.5% | hard block |
| Queue wait p95 | <= 300 ms | hard block |
| Tenant starvation | 0 | hard block |

## Admission and fairness gates

- Per-tenant turn request rate limit enforced (`TenantRateLimiter`).
- Per-tenant active run cap enforced (`max_active_runs_per_tenant`).
- BYOC fair admission enabled for contention-sensitive runtimes.
- Rejection semantics:
  - `429`: tenant rate/concurrency admission rejection
  - include deterministic retry hint (`retry_after_seconds`) where applicable
  - `503`: runtime dependency unavailable

## Autoscaling signal set

The following metrics are required for autoscaling decisions:

- queue depth
- queue wait time
- active run count
- timeout ratio
- error ratio
- CPU saturation (worker/runtime process)

## Deterministic hot-path constraints

- No blocking DB/network calls in the deterministic tool execution hot loop.
- Policy checks should remain O(1)/bounded with preloaded config.
- Execution adapter calls must return normalized envelopes without provider-specific leakage.

## Load profile validation (required before rollout)

Run 3 profiles and capture evidence:

1. **1 tenant**: baseline latency and correctness.
2. **10 tenants**: fairness and admission behavior under moderate contention.
3. **100 tenants**: bounded queue behavior and rejection stability under stress.

Evidence must include:

- command and runtime profile config
- pass/fail against SLO table
- observed rejection distribution by tenant
- rollback recommendation (`promote` or `hold`)

