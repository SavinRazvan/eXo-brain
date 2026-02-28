# eXo-brain

Provider-neutral orchestration framework for deterministic tool execution, multi-adapter runtime flows, and background multi-agent workloads.

## What this repository provides
- Provider-neutral runtime contracts and adapter boundary.
- Deterministic-first tool execution for state-changing/high-impact operations.
- Policy middleware with auditable decisions (`allow`, `deny`, `escalate`).
- MCP integration boundary with trust-tier and per-server health controls.
- Background runtime primitives (task graph, scheduler, worker pool, checkpoint/resume).

## Quick start
1. Create a Python virtual environment and install project dependencies.
2. Copy `.env.template` to `.env` and set required values.
3. Run tests:
   - `python -m pytest -q`
4. Run architecture checks:
   - `python scripts/architecture/validate_layers.py`
   - `python scripts/architecture/scan_forbidden_imports.py`

## Architecture principles
- Keep provider SDK specifics inside `src/runtime/*adapter*` modules.
- Keep orchestration core provider-neutral.
- Route state-changing/high-impact tool operations through deterministic policy-governed execution.
- Preserve strict layer boundaries (`integration -> core -> runtime/tools/policies/persistence/observability`).

## PR workflow
- Use PR-first delivery and branch-per-slice.
- Produce and keep `.local/review.md`, `.local/prep.md`, `.local/merge.md`.
- Merge only after tests and architecture checks pass.
