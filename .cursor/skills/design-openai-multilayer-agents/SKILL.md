---
name: design-openai-multilayer-agents
description: Designs a modular multi-layer agent architecture using OpenAI Agents SDK with explicit orchestration, routing, policy, tool runtime, and observability boundaries. Use when creating architecture blueprints or interface contracts.
---
# Design OpenAI Multilayer Agents

## Objective
Design a dynamic, plug-and-play multi-layer agent system with clean contracts.

## Required Layers
- Orchestration core
- Runtime adapter layer
- Handoff and routing layer
- Deterministic tool runtime layer
- Policy and safety middleware
- Schema contracts
- Observability and evaluation
- Background runtime and scheduler layer
- MCP integration layer

## Design Rules
1. Keep runtime provider details behind adapters.
2. Use typed contracts for tool IO and outputs.
3. Enforce deterministic execution for side-effecting tools.
4. Add fallback routes for handoff failures.
5. Include test/eval gates per architecture milestone.
6. Define explicit background execution contracts for parallel agents and cancellation.
7. Include plugin lifecycle contracts (`load`, `unload`, `reload`, compatibility checks).
8. Keep the framework embeddable as a module/SDK, not tied to any fixed UI/API.
9. Require logging/timeline contracts for parallel debugging and maintainability.
10. Support MCP servers (external and custom) through normalized adapters.
11. Support decorator-driven tool extensibility (security, validation, retries, auditing).
12. Keep OpenAI Agents SDK features configurable and available through capability flags.
13. Include open-source LLM adapter strategy (OpenAI-compatible and custom runtimes) through the same runtime contracts.
14. Require a provider capability matrix before enabling provider-native execution modes in production.

## Output Format
- Layered architecture diagram
- Package structure proposal
- Core interfaces
- Migration strategy
- Validation metrics
- Background runtime model (`TaskGraph`, scheduler, worker pool, checkpointing)
