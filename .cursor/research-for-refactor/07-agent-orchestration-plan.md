# Agent Orchestration Plan

## Goal
Define how architecture/planning agents collaborate efficiently with clear handoffs and no overlap.

## Operating Principles
- KISS by default.
- Event-driven coordination between planning stages.
- Deliver artifacts that are immediately consumable by the next agent.

## Agent Sequence

### Stage 1: `ArchitectureResearcher`
**Input**
- Existing docs, code references, current constraints.

**Output (required)**
- Reuse map (`direct`, `wrap`, `rewrite`)
- High-level architecture proposal
- Open risks/unknowns

**Exit Gate**
- Interface boundaries are clear enough for tooling/runtime decisions.

### Stage 2: `ToolingStrategist`
**Input**
- Stage 1 architecture proposal + reuse map.

**Output (required)**
- Tool/runtime mode strategy (`openai_native` vs `deterministic`)
- Plugin contracts (`agents`, `tools`)
- Policy and safety execution model

**Exit Gate**
- Tool execution paths are deterministic where needed and plugin lifecycle is defined.

### Stage 3: `MigrationArchitect`
**Input**
- Stage 1 + Stage 2 outputs.

**Output (required)**
- Phased migration plan
- Milestone dependencies and rollback plans
- Quality gates and release criteria

**Exit Gate**
- Each milestone is independently testable and releasable.

## Artifact Contract Between Stages
- Use normalized section names:
  - `Context`
  - `Decisions`
  - `Interfaces`
  - `Risks`
  - `Next Actions`
- Include a short machine-readable summary block:
  - `status`
  - `blockers`
  - `required_inputs`
  - `produced_outputs`

## Escalation Rules
- If a stage cannot proceed due to missing requirements, stop and emit `blocked` status.
- Do not invent unknown requirements; mark assumptions explicitly.
