# Provider Registry and Settings Schema (V1)

## Goal
Define a concrete, implementation-ready configuration contract for provider adapters, runtime mode selection, and user enablement flows.

## Scope
- `src/config/settings.py`: global runtime settings and safety defaults.
- `src/config/provider_registry.py`: provider registration, adapter wiring, and validation.
- Environment-driven deployment profiles (`local`, `staging`, `production`).

## Design Principles
- Provider-neutral core: config selects adapters; orchestration never branches on provider name.
- Safety-first defaults: deterministic execution is mandatory for risky/state-changing tool calls.
- Explicit enablement: providers are disabled unless declared and validated.
- Environment parity: the same schema works for managed and self-hosted providers.

## Settings Schema (YAML shape)
```yaml
schema_version: "1.0"
environment: "local"   # local|staging|production

runtime:
  default_provider_id: "openai_main"
  allowed_provider_ids: ["openai_main", "gemini_main"]
  mode_selector: "capability_policy_driven"   # capability_policy_driven|deterministic_only|provider_native_preferred
  fallback_provider_id: "openai_main"
  require_provider_healthcheck_on_start: true
  submit_tool_results_timeout_ms: 30000

policy:
  deterministic_required_for:
    state_changing: true
    risk_tiers: ["high", "critical"]
  allow_provider_native_for_read_only_low_risk: true
  block_on_capability_unknown: true
  escalation_channel: "security-review"

observability:
  require_correlation_ids: true
  log_provider_decisions: true
  emit_mode_selection_reasons: true

limits:
  max_parallel_jobs: 20
  max_concurrent_risky_tools_per_session: 1
  default_tool_timeout_ms: 30000
```

## Provider Registry Schema (YAML shape)
```yaml
schema_version: "1.0"
providers:
  - provider_id: "openai_main"
    display_name: "OpenAI Primary"
    adapter_class: "OpenAIAgentsRuntimeAdapter"
    enabled: true
    profile: "managed_vendor"   # managed_vendor|self_managed|local_only
    priority: 100
    endpoint:
      base_url: "https://api.openai.com/v1"
      api_type: "openai_native"   # openai_native|openai_compatible|custom
    auth:
      type: "api_key_env"
      api_key_env_var: "OPENAI_API_KEY"
    model_defaults:
      model: "gpt-4o"
      temperature: 0.2
      max_output_tokens: 1500
    capabilities_override: null
    rollout:
      stage: "production"   # local|staging|production
      traffic_percent: 100

  - provider_id: "gemini_main"
    display_name: "Gemini Primary"
    adapter_class: "GeminiRuntimeAdapter"
    enabled: false
    profile: "managed_vendor"
    priority: 80
    endpoint:
      base_url: "https://generativelanguage.googleapis.com"
      api_type: "custom"
    auth:
      type: "api_key_env"
      api_key_env_var: "GEMINI_API_KEY"
    model_defaults:
      model: "gemini-2.5-pro"
      temperature: 0.2
      max_output_tokens: 1500
    capabilities_override:
      supports_handoffs: false
    rollout:
      stage: "staging"
      traffic_percent: 10
```

## Required Fields (Provider Record)
- `provider_id`: stable identifier used in routing and audit logs.
- `adapter_class`: runtime adapter implementation name.
- `enabled`: activation gate.
- `endpoint`: provider/network endpoint definition.
- `auth`: credential source definition (never raw secret values).
- `model_defaults`: default model/runtime tuning.
- `rollout`: staged activation controls.

## Optional Fields
- `capabilities_override`: temporary capability patch when provider metadata is incomplete.
- `priority`: deterministic tie-break when multiple providers are eligible.
- `tags`: workload routing hints (`low_cost`, `high_accuracy`, `regulated_data_allowed`).

## Validation Rules
1. `default_provider_id` must exist and be `enabled=true`.
2. Startup must require `healthcheck()` for `default_provider_id` and any provider currently routed by profile/traffic rules.
3. `allowed_provider_ids` must be subset of configured provider IDs.
4. `adapter_class` must implement runtime adapter contract.
5. Secrets must come from env/Vault/KMS references, never plain config values.
6. If `block_on_capability_unknown=true`, unknown capability fields force deterministic mode.

## Healthcheck Policy (Long-Term)
- Providers not in active routing can remain `enabled=true` and `degraded` without blocking platform startup.
- `default_provider_id` health failure is startup-blocking unless an explicit healthy fallback is configured.
- If both default and fallback are unhealthy, startup must fail closed.
- Health status transitions must emit structured events for ops automation.

## User Enablement Flow (Provider Onboarding)
1. Add provider record to `provider_registry`.
2. Set `enabled=false` initially.
3. Configure credential env vars/secret references.
4. Run adapter conformance checklist (`32-*`).
5. Run workflow parity suite against baseline provider.
6. Promote rollout stage (`local` -> `staging` -> `production`) and increment traffic.

## Runtime Selection Flow (At Execution Time)
1. Choose candidate provider from `allowed_provider_ids` and routing hints.
2. Fetch capability map from adapter (`get_capabilities`).
3. Apply policy rules and requested tool risk.
4. Select `provider_native` or `deterministic` mode.
5. Record decision reason in logs/trace.
6. Execute and fallback to `fallback_provider_id` on provider degradation (when policy allows).

## Pydantic Model Outline (Python)
```python
class RuntimeSettings(BaseModel):
    default_provider_id: str
    allowed_provider_ids: list[str]
    mode_selector: Literal["capability_policy_driven", "deterministic_only", "provider_native_preferred"]
    fallback_provider_id: str | None = None
    require_provider_healthcheck_on_start: bool = True

class ProviderRecord(BaseModel):
    provider_id: str
    adapter_class: str
    enabled: bool
    profile: Literal["managed_vendor", "self_managed", "local_only"]
    endpoint: EndpointConfig
    auth: AuthConfig
    model_defaults: ModelDefaults
```

## Test Requirements
- Unit: settings/provider schema validation.
- Unit: startup validation failures (missing provider, missing secret ref, bad adapter class).
- Integration: enable/disable provider without core code change.
- Integration: fallback provider activation on degraded health status.
- Regression: policy-driven deterministic routing unchanged across provider swaps.

## Related Docs
- `10-provider-capability-matrix.md`
- `12-bootstrap-checklist.md`
- `31-tool-calling-contracts-and-mode-selection.md`
- `32-adapter-conformance-checklist.md`
- `33-mode-selection-policy-examples.md`
