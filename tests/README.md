# Test Module Split

Tests are physically organized by source module under `tests/modules/<module>/`.

## Layout

- `tests/modules/core/`
- `tests/modules/runtime/`
- `tests/modules/mcp/`
- `tests/modules/policies/`
- `tests/modules/...`
- `tests/modules/unknown/` for script and cross-cutting tests that do not map to one `src` module.

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
- Tests with no clear module mapping are marked as `module_unknown`.
