<!--
File: runtime.md
Path: docs/modules/runtime.md
Role: Module-level contract and maintenance guide for runtime adapters and tenant runtime composition.
Used By:
 - Maintainers modifying provider adapters and runtime mode selection
Depends On:
 - src/runtime/
 - tests/modules/runtime/
Notes:
 - Runtime adapters own provider SDK integrations; orchestration layers remain provider-neutral.
-->

# Runtime Module

## Metadata

- Status: `active`
- Owner: Savin I. Razvan
- Last validated commit: `HEAD`

## Primary Code Paths

- `src/runtime/runtime_adapter.py`
- `src/runtime/openai_agents_runtime.py`
- `src/runtime/openai_compatible_runtime.py`
- `src/runtime/tenant_runtime.py`
- `src/runtime/tool_wiring.py`
- `src/runtime/mode_selector.py`

## Primary Tests

- `tests/modules/runtime/`
- `tests/packages/test_openai_adapter_conformance.py`

## Contract Boundaries

- Runtime contract methods:
  - `start_session`
  - `run_turn`
  - `submit_tool_results`
  - `get_capabilities`
  - `healthcheck`
- Provider-specific code must remain in runtime adapter modules only.
- Mode selection must be capability/policy driven, never provider-name hardcoded.

## Operational Links

- `docs/runtime_contracts.md`
- `docs/plans/option-c-contract-freeze.md`
- `docs/plans/option-c-worker-isolation-contract.md`

## Breaking-Change Policy

- Any runtime contract signature or event behavior change requires:
  - conformance tests update
  - docs update (`docs/runtime_contracts.md` and this file)
  - verification against at least one non-provider-specific path
