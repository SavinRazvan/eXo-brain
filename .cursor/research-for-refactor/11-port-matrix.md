# Port Matrix: FlexiAI Toolsmith -> New Agent Framework

## Goal
Provide a concrete migration matrix that classifies source assets into:
- `reuse`: can be carried with minimal wrapping
- `adapt`: keep the pattern but redesign for new boundaries
- `do_not_reuse`: keep as reference only

This matrix is implementation-oriented and maps each source area to a destination module in the new repository.

## Classification Rules
- `reuse`: pattern and code shape already fit embeddable, modular architecture.
- `adapt`: valuable pattern exists, but current implementation is coupled to legacy runtime/UI/global state.
- `do_not_reuse`: domain-specific, UI-specific, or architecture-conflicting for the new framework.

## Port Matrix

| Source Path | Classification | Destination in New Repo | Why | Priority |
|---|---|---|---|---|
| `flexiai/core/handlers/event_dispatcher.py` | `reuse` | `src/core/event_router.py` | Clean event type to handler routing map | P0 |
| `flexiai/core/events/event_models.py` | `adapt` | `src/schemas/events.py` | Good typed event concept; expand for job/task/plugin correlation | P0 |
| `flexiai/core/events/rolling_event_buffer.py` | `adapt` | `src/observability/timeline.py` | Strong replay/timeline concept; needs concurrency-safe storage | P1 |
| `flexiai/core/handlers/tool_call_executor.py` | `adapt` | `src/tools/executor.py` | Deterministic execution model is key; add policy/decorator chain | P0 |
| `flexiai/toolsmith/tools_registry.py` | `adapt` | `src/tools/registry.py` | Useful registry concept; replace static mapping with plugin descriptors | P0 |
| `flexiai/toolsmith/tools_manager.py` | `adapt` | `src/tools/plugins/*` + `src/agents/plugins/*` | Valuable operation patterns, but currently monolithic and domain-mixed | P1 |
| `flexiai/config/models.py` | `reuse` | `src/config/settings.py` | Strong typed settings pattern via Pydantic | P0 |
| `flexiai/config/client_settings.py` | `adapt` | `src/config/provider_registry.py` | Keep provider selection idea, remove global singleton loading style | P1 |
| `flexiai/credentials/credentials.py` | `adapt` | `src/runtime/provider_registry.py` | Strategy pattern is correct; add capability map and adapter lifecycle | P0 |
| `flexiai/utils/context_utils.py` | `adapt` | `src/tools/decorators.py` or `src/policies/middleware.py` | Useful truncation guard; convert to configurable output policy | P2 |
| `flexiai/config/logging_config.py` | `adapt` | `src/observability/logging.py` | Keep rotating/structured logging idea; rework for async multi-worker runtime | P1 |
| `flexiai/core/handlers/run_thread_manager.py` | `adapt` | `src/runtime/openai_agents_runtime.py` + `src/core/session_store.py` | Good session/thread lifecycle shape; currently Assistants-specific | P0 |
| `flexiai/core/handlers/event_handler.py` | `adapt` | `src/core/orchestrator.py` + `src/runtime/*` | Central orchestration reference; split responsibilities by layer | P0 |
| `flexiai/channels/base_channel.py` | `adapt` | `src/integration/host_adapter.py` | Useful output boundary abstraction; rename to host integration contract | P1 |
| `flexiai/channels/channel_manager.py` | `do_not_reuse` | N/A (reference only) | Tied to app channel config, not embeddable core requirement | P3 |
| `flexiai/channels/multi_channel_publisher.py` | `adapt` | `src/integration/event_sink_router.py` (optional) | Fan-out pattern is useful for host adapters | P2 |
| `flexiai/core/events/event_bus.py` | `do_not_reuse` | N/A (reference only) | In-memory global bus does not fit distributed/background design | P3 |
| `flexiai/core/events/sse_manager.py` | `do_not_reuse` | N/A (host-level transport concern) | SSE queue is transport-specific, not core runtime | P3 |
| `flexiai/controllers/*` | `do_not_reuse` | N/A (host app concern) | CLI/Quart controllers are outside new embeddable SDK scope | P3 |
| `flexiai/toolsmith/tools_infrastructure/csv_infrastructure/csv_entrypoint.py` | `adapt` | `src/tools/plugins/csv_plugin.py` | Dispatcher + error envelope pattern is reusable | P2 |
| `flexiai/toolsmith/tools_infrastructure/spreadsheet_infrastructure/spreadsheet_entrypoint.py` | `adapt` | `src/tools/plugins/spreadsheet_plugin.py` | Dispatcher pattern reusable; domain logic should be isolated plugin | P2 |
| `flexiai/toolsmith/tools_infrastructure/security_audit.py` | `adapt` | `src/tools/decorators.py` + `src/tools/plugins/security_plugin.py` | Structured audit decorator pattern is high-value | P1 |
| `agents_experiments/OpenAI_AgentsSDK/handoffs_coordination.py` | `adapt` | `src/agents/handoff_router.py` tests/examples | Good handoff patterns; convert to production contracts | P1 |
| `agents_experiments/OpenAI_AgentsSDK/structured_outputs.py` | `adapt` | `src/schemas/outputs.py` + conformance tests | Strong structured output examples; formalize versioned schemas | P1 |
| `agents_experiments/OpenAI_AgentsSDK/async_agents.py` | `adapt` | `tests/performance/` + `src/core/task_scheduler.py` | Concurrency behavior references; move into scheduler benchmarks | P1 |
| `agents_experiments/OpenAI_AgentsSDK/guardrails_safety.py` | `adapt` | `src/policies/guardrails.py` | Convert examples into policy middleware contract and tests | P1 |
| `agents_experiments/OpenAI_AgentsSDK/tools_and_functions.py` | `do_not_reuse` | N/A (example set only) | Demo tools, not production contracts | P3 |
| `agents_experiments/OpenAI_AgentsSDK/performance_monitoring.py` | `adapt` | `src/observability/metrics.py` + perf tests | Metric dimensions are useful; integrate with runtime correlation IDs | P2 |

## Migration Sequence (Port-Aware)
1. Implement P0 targets first (`runtime`, `core`, deterministic `tools` path, provider strategy).
2. Add P1 targets (`observability`, plugins, guardrails, handoff robustness).
3. Add P2 targets (domain plugins and optional sink fan-out).
4. Keep P3 files as reference only; do not copy into core repo.

## Acceptance Checklist
- Every `adapt` item has an explicit destination module and contract owner.
- No `do_not_reuse` item is copied into core runtime package.
- P0 scope is sufficient for first vertical slice:
  - host adapter -> orchestrator -> runtime adapter -> deterministic tool execution -> logs/timeline.

## Related Docs
- `01-flexiai-reusable-assets.md`
- `02-target-architecture.md`
- `03-tool-calling-decision.md`
- `08-module-requirements-matrix.md`
- `10-provider-capability-matrix.md`

## References
- Upstream repository: https://github.com/SavinRazvan/flexiai-toolsmith
- Snapshot commit: `3f8b0c7a0996117dc95f0a8b93678dae44a5b0d6`
