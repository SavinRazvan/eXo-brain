# BYOC Artifact Integrity Dashboard Guide

## Purpose

Define the minimum dashboard and alert set for N3 rollout hardening of BYOC artifact-integrity parity checks.

## Required Panels

1. **Reason-Code Rate (5m / 1h)**
   - Group by `reason_code`
   - Must include:
     - `BYOC_ARTIFACT_INTEGRITY_MISMATCH`
     - `BYOC_ARTIFACT_INTEGRITY_MISSING`
     - `BYOC_ARTIFACT_SIGNATURE_VERSION_MISMATCH`
     - `BYOC_LEASE_INVALID_OR_EXPIRED`

2. **Top Affected Tenants**
   - Group by `tenant_id`
   - Split by reason-code family:
     - integrity mismatch
     - stale version
     - lease/idempotency

3. **Top Affected Tools/Versions**
   - Group by `tool_name`, `tool_version`
   - Include `artifact_signature_version`

4. **Worker Identity Heatmap**
   - Group by `worker_id` or worker token subject
   - Goal: isolate bad worker rollout quickly

5. **BYOC Claim -> Submit Success Funnel**
   - claimed jobs
   - accepted submits
   - rejected submits (by reason code)

6. **Tenant Cost Consumption**
   - Group by `tenant_id`
   - Include:
     - `tenant_cost_microunits_total`
     - `tenant_cost_limit_microunits`
     - `tenant_cost_remaining_microunits`
   - Goal: surface near-limit tenants before hard enforcement.

7. **Tenant Rejection Breakdown (Governance)**
   - Group by `tenant_id`
   - Split by `tenant_rejected_reason_*`
   - Must include:
     - `BYOC_COST_LIMIT_EXCEEDED`
     - `BYOC_LEASE_INVALID_OR_EXPIRED`
     - integrity/signature mismatch codes

## Alert Thresholds (Initial)

- P0 alert: any tenant with `BYOC_ARTIFACT_INTEGRITY_MISMATCH` > 5/min for 10 min.
- P1 alert: any tenant with `BYOC_ARTIFACT_SIGNATURE_VERSION_MISMATCH` > 2/min for 15 min.
- P1 alert: platform-wide integrity rejection rate > 2% of BYOC submit attempts over 15 min.
- P1 alert: any tenant with `tenant_cost_remaining_microunits` < 10% of limit for 30 min.
- P0 alert: sustained `BYOC_COST_LIMIT_EXCEEDED` rejections for a tenant (> 3/min for 10 min).

## Incident Correlation Fields

For all BYOC integrity alerts, include:
- `tenant_id`
- `job_id`
- `run_id`
- `call_id`
- `tool_name`
- `tool_version`
- `artifact_bundle_hash_sha256`
- `artifact_signature_version`
- `reason_code`
- `tenant_cost_microunits_total`
- `tenant_cost_limit_microunits`

## Runbook Linkage

- Primary response runbook:
  - `docs/operations/byoc-failure-injection-playbook.md`
  - section: `Escalation Criteria`
- Failure-injection drill playbook:
  - `docs/operations/byoc-failure-injection-playbook.md`

