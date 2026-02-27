---
name: research-flexiai-reuse
description: Researches the flexiai codebase to identify reusable modules, extension points, coupling risks, and migration candidates for new architectures. Use when auditing existing runtime/tooling code before refactors.
---
# Research FlexiAI Reuse

## Objective
Produce an actionable reuse map from `flexiai` for architecture planning.

## Workflow
1. Read architecture docs first:
   - `README.md`
   - `docs/ARCHITECTURE.md`
   - `docs/WORKFLOW.md`
2. Inspect implementation layers:
   - `flexiai/core/handlers`
   - `flexiai/toolsmith`
   - `flexiai/config`
   - `flexiai/credentials`
3. Classify components into:
   - Direct reuse
   - Reuse with wrapper
   - Rewrite
4. Extract key interfaces and extension points.
5. Report risks and compatibility constraints.
6. Explicitly assess background-concurrency limits and sequential bottlenecks.
7. Identify reusable pieces for plugin lifecycle and dynamic scaling.

## Output Format
- Reusable modules with file paths
- Reuse strategy per module
- Gaps and risks
- Recommended next migration step
- Background runtime readiness assessment
