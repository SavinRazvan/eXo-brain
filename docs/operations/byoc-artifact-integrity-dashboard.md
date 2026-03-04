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

## Alert Thresholds (Initial)

- P0 alert: any tenant with `BYOC_ARTIFACT_INTEGRITY_MISMATCH` > 5/min for 10 min.
- P1 alert: any tenant with `BYOC_ARTIFACT_SIGNATURE_VERSION_MISMATCH` > 2/min for 15 min.
- P1 alert: platform-wide integrity rejection rate > 2% of BYOC submit attempts over 15 min.

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

## Runbook Linkage

- Primary response runbook:
  - `.cursor/research-for-refactor/18-enterprise-operational-runbooks.md`
  - section: `8) BYOC Artifact Integrity Mismatch Runbook`

