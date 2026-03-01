# Phased Migration Plan (Concrete Interfaces)

## Phase 0: Baseline and Contracts
- Freeze baseline behavior from current experiments and `flexiai` runtime patterns.
- Define canonical schemas:
  - `RuntimeEvent`
  - `ToolCallContext`
  - `ToolResult`
  - `OutputEnvelope`
- Define interface contracts:
  - `RuntimeAdapter`
  - `ToolRuntime`
  - `PolicyMiddleware`
  - `HandoffRouter`

## Phase 1: Deterministic Tool Layer First
- Port `tools_registry` concept into descriptor-driven registry.
- Port `tool_call_executor` concept into unified execution runtime.
- Add per-tool metadata:
  - domain
  - risk level
  - timeout
  - idempotency
  - approval requirement
- Add standardized output envelope for all tools.

## Phase 2: Runtime Adapter Layer
- Implement `OpenAIAgentsRuntimeAdapter`.
- Add compatibility adapter only if needed for older assistant flows.
- Ensure orchestrator consumes normalized runtime events independent of backend SDK.
- Add runtime mode selector to support OpenAI-native and deterministic tool execution paths.

## Phase 3: Handoffs and Multi-Layer Routing
- Convert hardcoded handoff examples into config-driven routing tables.
- Add fallback routing policies and error routes.
- Add specialized agent registries by domain and capability tags.

## Phase 4: Guardrails, Safety, and Approval Gates
- Add pre-execution policy middleware and post-execution redaction.
- Enforce stricter gates for state-changing/high-impact operations.
- Add policy audit trail per request/session.

## Phase 5: Observability and Evaluation
- Add structured logging, tracing IDs, and timeline reconstruction across runtime, tools, and outputs.
- Add latency/throughput and tool success/failure metrics.
- Add regression scenarios for:
  - handoff correctness
  - schema validity
  - policy compliance
  - performance budgets

## Phase 6: Hardening and Promotion
- Run staged load testing and failure injection.
- Validate rollback/fallback behavior.
- Promote from research implementation to production-ready branch/repository structure.

## References
- Upstream repository: https://github.com/SavinRazvan/flexiai-toolsmith
- Snapshot commit: `3f8b0c7a0996117dc95f0a8b93678dae44a5b0d6`
- Migration baseline references:
  - https://github.com/SavinRazvan/flexiai-toolsmith/blob/3f8b0c7a0996117dc95f0a8b93678dae44a5b0d6/docs/ARCHITECTURE.md
  - https://github.com/SavinRazvan/flexiai-toolsmith/blob/3f8b0c7a0996117dc95f0a8b93678dae44a5b0d6/docs/WORKFLOW.md
  - https://github.com/SavinRazvan/flexiai-toolsmith/blob/3f8b0c7a0996117dc95f0a8b93678dae44a5b0d6/flexiai/core/handlers/event_handler.py
  - https://github.com/SavinRazvan/flexiai-toolsmith/blob/3f8b0c7a0996117dc95f0a8b93678dae44a5b0d6/flexiai/core/handlers/run_thread_manager.py
