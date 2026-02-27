---
name: plan-refactor-migration
description: Produces phased refactor plans with milestone gates, rollback safety, and file-level migration order. Use when converting experiments into production-ready modular systems.
---
# Plan Refactor Migration

## Objective
Build incremental migration plans that preserve behavior while improving architecture.

## Planning Steps
1. Define baseline behavior and non-negotiable requirements.
2. Break work into independently verifiable milestones.
3. For each milestone, specify:
   - Scope
   - Files/components touched
   - Risks
   - Rollback path
   - Acceptance checks
4. Prioritize adapter layers before deep rewrites.
5. Include observability and performance checkpoints.
6. Include background runtime milestones (scheduler, worker pool, checkpointing, cancellation).
7. Include plugin lifecycle milestones (load/unload/reload and compatibility validation).
8. Include logging/timeline milestones to debug parallel task execution.

## Output Format
- Milestone-by-milestone plan
- File migration map
- Risk register
- Exit criteria per milestone
- Concurrency and reliability gates
