# Provider Capability Matrix

## Goal
Define a capability-based model/provider selection strategy so the framework can plug in or plug out OpenAI and open-source LLM backends without changing orchestration core.

## Why This Matters
- OpenAI Agents SDK is high-capability but provider-specific.
- Open-source models and OpenAI-compatible endpoints vary in tool-calling and schema reliability.
- A capability matrix lets runtime choose safe execution mode per task (`provider_native` vs `deterministic`).

## Runtime Adapter Strategy
- Keep OpenAI Agents SDK behind `OpenAIAgentsRuntimeAdapter`.
- Use `OpenAICompatibleRuntimeAdapter` for OpenAI-style APIs (for example vLLM servers).
- Use `CustomAgentRuntimeAdapter` when provider features are missing or unstable.
- The `runtime/mode_selector.py` decides execution mode from policy + capability map.

## Capability Dimensions
- `supports_agents_sdk_native`
- `supports_openai_compatible_api`
- `supports_streaming`
- `supports_function_calling`
- `supports_structured_output`
- `supports_handoffs`
- `max_context_tokens`
- `reliability_score` (1-5)
- `security_tier` (`managed_vendor`, `self_managed`, `local_only`)
- `recommended_runtime_mode` (`provider_native`, `deterministic`, `hybrid`)

## V1 Provider Matrix (Initial Defaults)

| Provider | Model Family | Access Path | Runtime Adapter | Agents SDK Native | Tool Calling | Structured Output | Streaming | Reliability (1-5) | Security Tier | Recommended Runtime Mode | Notes |
|---|---|---|---|---|---|---|---|---:|---|---|---|
| OpenAI | GPT-4.x / GPT-4o | OpenAI API | `OpenAIAgentsRuntimeAdapter` | Yes | High | High | Yes | 5 | `managed_vendor` | `hybrid` | Baseline reference provider |
| Azure OpenAI | GPT-4.x | Azure API | `OpenAIAgentsRuntimeAdapter` (or Azure-specific adapter) | Partial | High | High | Yes | 5 | `managed_vendor` | `hybrid` | Enterprise controls and regional deployment |
| vLLM (self-hosted) | Llama / Qwen / Mistral | OpenAI-compatible endpoint | `OpenAICompatibleRuntimeAdapter` | No | Medium | Medium | Yes | 3 | `self_managed` | `deterministic` | Strong infra flexibility, capability varies by model |
| TGI (self-hosted) | OSS models | HF endpoint | `CustomAgentRuntimeAdapter` | No | Medium | Medium | Yes | 3 | `self_managed` | `deterministic` | Usually requires custom orchestration wrappers |
| llama.cpp local | GGUF models | Local server | `CustomAgentRuntimeAdapter` | No | Low-Med | Low-Med | Partial | 2 | `local_only` | `deterministic` | Best for local/offline, weaker advanced features |
| Ollama local/remote | OSS models | Ollama API | `CustomAgentRuntimeAdapter` | No | Medium | Medium | Yes | 3 | `local_only` or `self_managed` | `deterministic` | Convenient local packaging and model switching |

## Decision Rules
- If operation is state-changing or security-sensitive, force deterministic tool runtime.
- If provider capability scores are below threshold (`tool_calling < 4` or `structured_output < 4`), route through deterministic mode.
- Allow openai-native mode only when provider supports needed features and policy permits.
- Keep fallback path available for any failed handoff/tool chain.

## Suggested Capability Map Schema

```yaml
provider_id: "oss_vllm_llama3_70b"
supports_agents_sdk_native: false
supports_openai_compatible_api: true
supports_streaming: true
supports_function_calling: true
supports_structured_output: partial
supports_handoffs: false
max_context_tokens: 128000
reliability_score: 3
security_tier: "self_managed"
recommended_runtime_mode: "deterministic"
```

## Required Adapter Contract
- `start_session(session_id: str, metadata: dict | None = None) -> SessionHandle`
- `run_turn(session_id: str, user_input: str, context: dict) -> AsyncIterator[RuntimeEvent]`
- `submit_tool_results(session_id: str, run_id: str, tool_results: list[ToolResult]) -> AsyncIterator[RuntimeEvent]`
- `get_capabilities() -> ProviderCapabilityMap`
- `healthcheck() -> HealthStatus`

## References
- Upstream repository: https://github.com/SavinRazvan/flexiai-toolsmith
- Snapshot commit: `3f8b0c7a0996117dc95f0a8b93678dae44a5b0d6`
- Existing architecture context:
  - https://github.com/SavinRazvan/flexiai-toolsmith/blob/3f8b0c7a0996117dc95f0a8b93678dae44a5b0d6/docs/ARCHITECTURE.md
  - https://github.com/SavinRazvan/flexiai-toolsmith/blob/3f8b0c7a0996117dc95f0a8b93678dae44a5b0d6/docs/WORKFLOW.md
