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

## CI Integration

- Workflow: `.github/workflows/rc-signoff.yml`
- Trigger: pull requests targeting `main` (plus push to `main` and manual dispatch)
- Behavior:
  - runs `make rc-signoff`
  - runs `make rc-signoff-json` to produce normalized JSON
  - uploads both `.local/rc-signoff.md` and `.local/rc-signoff.json` as artifact `rc-signoff-evidence` even on failure

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
- [ ] Attach `.local/rc-signoff.md` to release/PR records.
- [ ] Confirm required PR artifacts exist:
  - `.local/review.md`
  - `.local/prep.md`
  - `.local/merge.md`

## Notes

- The signoff command fails fast if a required evidence-link document is missing.
- On gate failure, `.local/rc-signoff.md` still contains outputs for debugging.
