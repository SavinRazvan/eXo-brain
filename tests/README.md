# Test Module Split

Tests are physically organized by source module under `tests/modules/<module>/`.

## Layout

- `tests/modules/core/`
- `tests/modules/runtime/`
- `tests/modules/mcp/`
- `tests/modules/policies/`
- `tests/modules/...`
- `tests/modules/integration/` for **cross-layer** flows (host adapter, orchestration + runtime + tools) that are not owned by a single `tests/modules/<src-module>/` bucket.
- `tests/modules/compliance/README.md` — evidence-bundle vs audit-suite ownership (**FIND-005**).
- `tests/modules/pr_workflow/`, `tests/modules/architecture_scripts/`, `tests/modules/release_scripts/`, `tests/modules/perf_scripts/` for **repository script** tests (`scripts/pr`, `scripts/architecture`, `scripts/release`, `scripts/perf`) that do not map to a single `src` module (pytest may still mark them `module_unknown` when no `src.*` import is inferred).

## Run all tests

```bash
pytest -q
```

## Run by module

```bash
pytest -q tests/modules/core
pytest -q tests/modules/runtime
pytest -q tests/modules/mcp
```

You can also use markers:

```bash
pytest -q -m module_core
```

## Optional duplicate guard

To fail collection when duplicate test function names exist in the same module bucket:

```bash
pytest -q --enforce-unique-test-names-per-module
```

## Notes

- Module markers are inferred from `src.<module>` imports in each test file.
- Tests with no `src.*` import inferred from the file are marked as `module_unknown` (common for script-only tests under `*_scripts/` / `pr_workflow/`).
