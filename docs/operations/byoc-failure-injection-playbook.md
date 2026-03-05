<!--
File: byoc-failure-injection-playbook.md
Path: docs/operations/byoc-failure-injection-playbook.md
Role: Operator playbook for injected BYOC failure triage using runtime-control and RC evidence artifacts.
Used By:
 - Platform operators running local/CI failure drills
 - Release signoff incident triage workflows
Depends On:
 - docs/operations/release-candidate-signoff-checklist.md
 - docs/operations/byoc-artifact-integrity-dashboard.md
 - src/api/routers/runtime_control.py
Notes:
 - This is process-only guidance; runtime behavior is unchanged.
-->

# BYOC Failure Injection Playbook

## Purpose

Provide a repeatable incident drill matrix for BYOC failures and map each failure class to:

- injection trigger
- runtime-control signals
- evidence artifacts
- remediation commands

Use this playbook during local rehearsals and CI investigation to keep triage deterministic.

## Preconditions

Run baseline readiness first:

```bash
make ui-smoke
```

Recommended evidence bootstrap:

```bash
make rc-signoff && make rc-signoff-json
```

## Runtime-Control Endpoints Used In Triage

- `GET /tenants/{tenant_id}/admin/runtime/control-stats`
- `GET /tenants/{tenant_id}/admin/byoc/governance-metrics`
- `GET /tenants/{tenant_id}/admin/byoc/dlq?limit=<n>`
- `POST /tenants/{tenant_id}/admin/byoc/dlq/{job_id}/replay`
- `POST /tenants/{tenant_id}/admin/byoc/cleanup`

## Failure Injection Matrix

| Failure class | Injection trigger | Expected signals | Evidence artifacts | First remediation |
|---|---|---|---|---|
| Lease retry exhaustion / DLQ growth | Run lease-storm scenario (`test_sqlite_job_store_lease_expiry_storm_routes_to_dlq`) | `dlq_moved_total` increases, DLQ records with `BYOC_LEASE_RETRY_EXHAUSTED` | pytest output, `/admin/byoc/dlq`, `.local/rc-signoff.md` | replay one job, inspect worker liveness/lease TTL |
| Replay-collision submit pressure | Run replay collision scenario (`test_byoc_runtime_sqlite_replay_collision_under_submit_pressure`) | submit errors `WORKER_REQUEST_REPLAYED`, rejection counters rise | pytest output, governance rejection reasons | verify nonce generation uniqueness on worker side |
| Artifact integrity mismatch | Run integrity mismatch scenario (`test_byoc_submit_rejects_artifact_integrity_mismatch`) | rejection reason `BYOC_ARTIFACT_INTEGRITY_MISMATCH` | dashboard panel + governance export + rc signoff | validate active bundle hash/signature and worker package version |
| Stale signature version | Run signature version mismatch scenario (`test_byoc_submit_rejects_signature_version_mismatch`) | rejection reason `BYOC_ARTIFACT_SIGNATURE_VERSION_MISMATCH` | governance export + rc signoff governance alerts | rotate/sync worker artifact metadata and signing version |
| Fair-admission contention timeout | Run fairness contention scenario (`test_byoc_runtime_control_stats_include_fairness_timeout_indicators_per_tenant`) | `fair_admission_timeout_total`, `tenant_fair_admission_timeout_total` increase | runtime control stats snapshot | tune `EXO_BYOC_FAIR_ADMISSION_WAIT_TIMEOUT_MS` and contention profile |
| Budget-window enforcement saturation | Run windowed budget scenario (`test_byoc_runtime_windowed_cost_limit_resets_and_enforces_window_reason`) | rejection reason `BYOC_COST_WINDOW_LIMIT_EXCEEDED`; window counters advance | governance metrics + rc signoff governance alerts | raise budget/window or reduce cost per operation |

## Drill Procedure (Per Failure Class)

1. **Inject**
   - Run only the targeted test:
   ```bash
   python -m pytest -q tests/modules/tools/test_byoc_runtime.py -k "<target>"
   ```
2. **Capture runtime signals**
   - Query control stats and governance metrics for affected tenant:
   ```bash
   curl -s "http://127.0.0.1:8787/tenants/t1/admin/runtime/control-stats" -H "X-Identity: <json>"
   curl -s "http://127.0.0.1:8787/tenants/t1/admin/byoc/governance-metrics" -H "X-Identity: <json>"
   ```
3. **Attach evidence**
   - Ensure artifacts exist:
     - `.local/rc-signoff.md`
     - `.local/rc-signoff.json`
     - `.local/ui-smoke-runtime-snapshots.json`
4. **Apply remediation**
   - Use the matrix remediation for that failure class.
5. **Verify recovery**
   - Re-run affected test and `make ui-smoke`.

## Soak + Failure Combined Drill

To validate behavior under sustained contention before/after failure injection:

```bash
EXO_RUN_SOAK_TESTS=true python -m pytest -q tests/modules/api/test_byoc_soak_suite.py
```

Then run one failure-injection test and confirm:

- no tenant starvation regression
- anomaly signals remain queryable
- fairness counters remain deterministic

## Escalation Criteria

Escalate to incident review when any condition persists after one remediation cycle:

- `BYOC_ARTIFACT_INTEGRITY_MISMATCH` sustained > 10 minutes
- DLQ growth monotonic over 3 replay attempts
- fairness timeout counters rising with no successful completions for one tenant
- governance anomaly report remains non-empty across two consecutive verification windows

## Related References

- `docs/operations/release-candidate-signoff-checklist.md`
- `docs/operations/byoc-artifact-integrity-dashboard.md`
- `.cursor/research-for-refactor/18-enterprise-operational-runbooks.md`
