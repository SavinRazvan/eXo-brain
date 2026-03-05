<!--
File: local-ui-readiness-smoke.md
Path: docs/operations/local-ui-readiness-smoke.md
Role: Operator guide for deterministic local UI readiness and first-turn smoke validation.
Used By:
 - Maintainers preparing local browser validation sessions
Depends On:
 - Makefile
 - scripts/ui/local_ui_readiness_smoke.py
Notes:
 - Keeps checks additive; does not change normal app startup behavior.
-->

# Local UI Readiness And Smoke

Use this before manual browser validation sessions to verify local prerequisites and an end-to-end baseline path.

## One-Command Run

```bash
make ui-smoke
```

This command runs:

1. UI asset check/build (`ui/dist/index.html`)
2. Temporary local API boot + `/health` readiness
3. `/ui` route validation
4. Tenant-scoped smoke path:
   - provider create (local custom adapter)
   - tool import/upload/validate/versions
   - agent create
   - session create
   - SSE first-turn stream (expects output + terminal event)
5. Runtime-control snapshot export for advisory evidence linkage:
   - `.local/ui-smoke-runtime-snapshots.json` with `before` and `after` captures

## Expected Output

Each stage emits a deterministic PASS/FAIL line:

- `[PASS] UI build` (or `[PASS] UI assets available`)
- `[PASS] API health`
- `[PASS] End-to-end smoke flow`

On failures, the script prints a short remediation hint for the failed stage.

## Useful Options

```bash
python scripts/ui/local_ui_readiness_smoke.py --help
```

Common flags:

- `--host` / `--port`: run smoke against a custom local bind.
- `--tenant-id`: change tenant used by smoke resources.
- `--skip-ui-build`: fail fast if UI dist is missing instead of building.
- `--startup-timeout-seconds`: increase API boot wait time on slow machines.
- `--request-timeout-seconds`: increase API request/SSE timeout.

## Notes

- The script starts and stops a temporary API process automatically.
- Smoke resources use timestamped IDs to avoid clashing with existing records.
- Runtime snapshot export is advisory; endpoints may return `409` when specific adapters are disabled.
- This is a readiness gate only; it does not replace full test/architecture gates.
