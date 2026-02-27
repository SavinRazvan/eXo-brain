# Module Requirements Matrix

## Goal
Define explicit requirements per module so architecture and implementation stay modular, dynamic, and scalable.

## Core Module Requirements

## `integration/`
- Purpose: host-app embedding boundary.
- Must:
  - remain transport-agnostic
  - support `HTTP`, `SSE`, `WebSocket`, and async worker adapters
  - avoid orchestration logic

## `core/`
- Purpose: orchestration and background execution.
- Must:
  - support `TaskGraph`, scheduler, worker pool, cancel/resume
  - expose event-driven state transitions
  - enforce bounded concurrency

## `runtime/`
- Purpose: model/runtime abstraction.
- Must:
  - provide `RuntimeAdapter` contract
  - implement `start_session`, `run_turn`, `submit_tool_results`, `get_capabilities`, `healthcheck`
  - support runtime mode selector (`provider_native` / `deterministic`)
  - expose OpenAI Agents SDK capabilities via feature flags/capability map
  - support plug-in adapters for open-source/openai-compatible runtimes
  - expose provider capability metadata (`tool_calling`, `structured_output`, `handoffs`, `streaming`)
  - keep provider details isolated

## `agents/`
- Purpose: specialist roles and routing.
- Must:
  - support agent plugin registration
  - expose handoff routes and fallback paths
  - support capability tags and domain routing

## `tools/`
- Purpose: deterministic tool execution.
- Must:
  - use descriptor-driven registry
  - enforce tool intent/output contracts (`ToolCallContext`, `ToolResult`, normalized error envelope)
  - support tool plugin lifecycle
  - support decorator-based extension points (security, validation, retries, audit)
  - enforce standardized output envelope

## `mcp/`
- Purpose: MCP server integration boundary.
- Must:
  - register external and custom MCP servers
  - expose MCP tools through normalized tool descriptors
  - enforce trust tiers and network/security policy
  - provide per-server health and timeout controls

## `persistence/`
- Purpose: durable state and audit/event persistence across local and remote database backends.
- Must:
  - expose provider-agnostic store contracts (`SessionStore`, `CheckpointStore`, `WorkflowStore`, `AuditStore`, `EventStore`)
  - support adapter-based backends (`postgres`, `sqlite`, and future backends)
  - enforce schema versioning and migration compatibility
  - support tenant isolation and retention policies
  - support atomic writes for checkpoint and audit-critical paths

## `policies/`
- Purpose: safety and control gates.
- Must:
  - run pre/post tool execution checks
  - return explicit decisions (`allow`, `deny`, `escalate`) with reason codes
  - run policy checks for MCP-routed tool calls
  - support risk-based escalation
  - produce auditable decisions

## `schemas/`
- Purpose: contracts for portability and stability.
- Must:
  - define typed IO for runtime, tools, workflows
  - support schema versioning
  - validate workflow load inputs

## `observability/`
- Purpose: debugability and operations.
- Must:
  - provide structured logs with correlation IDs
  - support timeline reconstruction for parallel runs
  - expose metrics and traces

## `config/`
- Purpose: environment and feature toggles.
- Must:
  - keep defaults simple (KISS)
  - support feature flags for advanced runtime behavior
  - isolate provider- and host-specific settings

## Non-Functional Requirements (Global)
- Modular: each module can evolve independently.
- Dynamic: runtime mode and plugins selectable at run-time.
- Scalable: bounded concurrency and adaptive strategies.
- Maintainable: every module has logs + tests + clear interfaces.
