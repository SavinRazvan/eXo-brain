# Release Candidate Signoff Checklist

## Purpose

Provide one command for release-candidate signoff and one evidence artifact path for approval records.

## One-Command Signoff

Run:

```bash
make rc-signoff
```

This executes:

- `python -m pytest -q`
- `python scripts/architecture/validate_layers.py`
- `python scripts/architecture/scan_forbidden_imports.py`

and writes:

- `.local/rc-signoff.md`
- `.local/rc-signoff.json` (via `make rc-signoff-json`)

The generated artifact includes execution metadata for auditability:

- actor
- repository
- event/ref
- commit SHA
- PR number (when provided by CI env)
- workflow run id/url

For dashboard/alert ingestion, run:

```bash
make rc-signoff-json
```

This parses `.local/rc-signoff.md` into a normalized JSON summary at `.local/rc-signoff.json`.
The normalized payload now includes per-gate execution metadata (`command`, `exit_code`, `duration_ms`)
to support alerting and trend dashboards.

RC evidence also includes a `Local Data Safety` section with:
- backup/restore validation command metadata
- advisory/required mode flag
- normalized parser output under `data_safety` in `.local/rc-signoff.json`

RC evidence now also includes a `Governance Alerts` section with:
- advisory threshold evaluation against BYOC governance metrics (`cost.utilization_ratio`, `submissions.rejection_rate`)
- normalized parser output under `governance_alerts` in `.local/rc-signoff.json`
- advisory-only behavior when governance metrics input is unavailable or incomplete

RC evidence also includes a `Runtime Snapshots` section with:
- advisory linkage to historical local UI smoke runtime snapshots (`before`/`after`)
- default input path `.local/ui-smoke-runtime-snapshots.json`
- normalized parser output under `runtime_snapshots` in `.local/rc-signoff.json`

RC evidence now also includes a `UI E2E Automation` section with:
- advisory linkage to the normalized UI automation lane artifact
- default input path `.local/ui-e2e-smoke.json`
- normalized parser output under `ui_e2e_automation` in `.local/rc-signoff.json`

For Option C API-first operation, both `Runtime Snapshots` and `UI E2E Automation` are
archival/advisory inputs only and are not required execution gates unless a dedicated UI
track is explicitly re-enabled.

Default governance metrics input path:

```bash
.local/byoc-governance-metrics.json
```

Override path at runtime:

```bash
python scripts/release/rc_signoff.py --governance-metrics-in .local/custom-governance-metrics.json --out .local/rc-signoff.md
```

Default behavior is advisory (non-blocking). To make data safety mandatory:

```bash
EXO_RC_SIGNOFF_REQUIRE_DATA_SAFETY=true make rc-signoff
```

## CI Integration

- Workflow: `.github/workflows/rc-signoff.yml`
- Trigger: pull requests targeting `main` (plus push to `main` and manual dispatch)
- Behavior:
  - runs `make rc-signoff`
  - runs `make rc-signoff-json` to produce normalized JSON
  - uploads both `.local/rc-signoff.md` and `.local/rc-signoff.json` as artifact `rc-signoff-evidence` even on failure
- Advisory soak lane: `.github/workflows/byoc-soak-nonblocking.yml`
  - Trigger: nightly schedule + manual dispatch
  - runs `pytest -m soak` with `EXO_RUN_SOAK_TESTS=true`
  - uploads `.local/byoc-soak.log` and `.local/byoc-soak-summary.txt` for triage
  - non-blocking by design (does not gate PR merges)
To hard-block merges, set `rc-signoff / rc_signoff` as a required status check in branch protection for `main`.

## Required Evidence-Link Documents

The signoff runner verifies these files exist before running gates:

- `docs/plans/tenant-tool-execution-architecture.md`
- `docs/operations/byoc-artifact-integrity-dashboard.md`
- `.cursor/research-for-refactor/18-enterprise-operational-runbooks.md`
- `.cursor/research-for-refactor/26-deployment-profiles-matrix.md`
- `.cursor/research-for-refactor/12-bootstrap-checklist.md`
- `.cursor/research-for-refactor/06-mvp-build-sequence.md`

## Operator Checklist

- [ ] Run `make rc-signoff`.
- [ ] Confirm `.local/rc-signoff.md` exists and `Overall` is `PASS`.
- [ ] Confirm `Local Data Safety` section is present and reviewed.
- [ ] Confirm `Governance Alerts` section is present and reviewed (advisory signal).
- [ ] Confirm `Runtime Snapshots` section is present and linked (advisory signal).
- [ ] Confirm `UI E2E Automation` section is present and linked (advisory signal).
- [ ] If BYOC anomalies/rejections are present, run the matching drill in `docs/operations/byoc-failure-injection-playbook.md`.
- [ ] Attach `.local/rc-signoff.md` to release/PR records.
- [ ] Confirm required PR artifacts exist:
  - `.local/review.md`
  - `.local/prep.md`
  - `.local/merge.md`

## Notes

- The signoff command fails fast if a required evidence-link document is missing.
- On gate failure, `.local/rc-signoff.md` still contains outputs for debugging.
