<!--
File: adapter-telemetry-dimensions.md
Path: docs/operations/adapter-telemetry-dimensions.md
Role: Recommended structured log / metric dimensions for provider adapter operations and debugging.
Used By:
 - Observability implementers, on-call, adapter authors
Depends On:
 - docs/strategy/adapter-compatibility-matrix.md
 - src/runtime/*
Notes:
 - Dimensions are advisory until uniformly wired in code; use as checklist for new logging.
-->

# Adapter telemetry dimensions

When logging or emitting metrics around **provider execution**, include these fields where available so incidents can be correlated across **tenant**, **adapter build**, and **contract version**.

## Recommended dimensions

| Dimension | Example | Purpose |
|-----------|---------|---------|
| `provider_id` | `openai-primary` | Which registered provider record was used |
| `adapter_package` | `exo-adapter-openai` | Installed adapter distribution name |
| `adapter_package_version` | `0.1.0` | Adapter semver (pyproject / import metadata) |
| `core_contracts_version` | `0.1.0` | `exo-brain-core-contracts` version the adapter was built against |
| `api_type` | `openai_native`, `openai_compatible`, `custom` | Protocol lane from `EndpointConfig` / registration (`src/config/provider_registry.py`) |
| `correlation_id` | request/turn correlation | Tie API → orchestration → audit |

## Optional (high-value for failover)

- `fallback_from_provider_id` / `fallback_to_provider_id` when failover occurs.
- `runtime_mode` or capability map snapshot hash when debugging mode selection.

## References

- Registration schema: `src/api/schemas/provider_schemas.py`
- Strategy matrix: [`docs/strategy/adapter-compatibility-matrix.md`](../strategy/adapter-compatibility-matrix.md)
