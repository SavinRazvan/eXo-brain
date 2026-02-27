# FlexiAI Reusable Assets

## High-Value Reuse Candidates

### Orchestration and Event Routing
- `flexiai/core/handlers/event_handler.py`
  - Strong central orchestration flow.
  - Handles streaming deltas, tool-call requirements, and publish pipeline.
- `flexiai/core/handlers/event_dispatcher.py`
  - Clean event-type to handler mapping.
  - Good base for normalized event contracts.
- `flexiai/core/handlers/handler_factory.py`
  - Useful composition point for dependency injection.

### Tool Execution and Deterministic Control
- `flexiai/core/handlers/tool_call_executor.py`
  - Deterministic `tool_name -> callable` execution model.
  - Consistent tool output envelope shaping.
- `flexiai/toolsmith/tools_registry.py`
  - Central registry for tool mapping.
  - Existing `refresh_tool_mappings()` can evolve to dynamic plugin reloading.
- `flexiai/toolsmith/tools_manager.py`
  - Practical facade with many real-world operations.
  - Existing multi-assistant primitives (`initialize_agent`, `communicate_with_assistant`) are useful references.

### Session, Streaming, and Replay Utilities
- `flexiai/core/events/rolling_event_buffer.py`
  - Strong concept for stream replay/resume and partial/final buffering.
- `flexiai/core/events/sse_manager.py`
  - Reusable SSE queueing idea for web channels.

### Config and Provider Strategy
- `flexiai/config/models.py`
  - Reusable Pydantic settings models.
- `flexiai/credentials/credentials.py`
  - Strategy-style provider selection with explicit credential validation.

## Reuse With Wrappers (Not Direct Copy)
- `flexiai/core/handlers/run_thread_manager.py`
  - Strong session/run manager pattern, but tightly coupled to Assistants API (`client.beta.threads`).
  - Reuse shape, not implementation.
- `flexiai/controllers/cli_chat_controller.py`
- `flexiai/controllers/quart_chat_controller.py`
  - Keep as integration adapters only; avoid putting orchestration decisions here in the new system.

## Current Gaps To Address In New Architecture
- Static tool registration (no metadata-driven plugin lifecycle).
- No centralized policy middleware before high-risk tool execution.
- Global/shared state patterns in some runtime paths reduce isolation.
- Mixed return envelopes in tool pipeline should be unified under one schema.

## References
- Upstream repository: https://github.com/SavinRazvan/flexiai-toolsmith
- Snapshot commit: `3f8b0c7a0996117dc95f0a8b93678dae44a5b0d6`
- Key files:
  - https://github.com/SavinRazvan/flexiai-toolsmith/blob/3f8b0c7a0996117dc95f0a8b93678dae44a5b0d6/flexiai/core/handlers/event_handler.py
  - https://github.com/SavinRazvan/flexiai-toolsmith/blob/3f8b0c7a0996117dc95f0a8b93678dae44a5b0d6/flexiai/core/handlers/event_dispatcher.py
  - https://github.com/SavinRazvan/flexiai-toolsmith/blob/3f8b0c7a0996117dc95f0a8b93678dae44a5b0d6/flexiai/core/handlers/tool_call_executor.py
  - https://github.com/SavinRazvan/flexiai-toolsmith/blob/3f8b0c7a0996117dc95f0a8b93678dae44a5b0d6/flexiai/toolsmith/tools_registry.py
  - https://github.com/SavinRazvan/flexiai-toolsmith/blob/3f8b0c7a0996117dc95f0a8b93678dae44a5b0d6/flexiai/toolsmith/tools_manager.py
  - https://github.com/SavinRazvan/flexiai-toolsmith/blob/3f8b0c7a0996117dc95f0a8b93678dae44a5b0d6/flexiai/config/models.py
  - https://github.com/SavinRazvan/flexiai-toolsmith/blob/3f8b0c7a0996117dc95f0a8b93678dae44a5b0d6/flexiai/credentials/credentials.py
