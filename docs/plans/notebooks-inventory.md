# Notebooks Inventory

## Current Notebook State

| Notebook | Current Purpose | Overlap | Runtime Requirement | Decision | Action |
|---|---|---|---|---|---|
| `notebooks/01_first_brick_core_framework.ipynb` | Core framework walkthrough + deterministic orchestration + DAG demo | Overlaps with new module notebooks for core/orchestrator and tenancy checks | No API key required | `merge` | Split reusable checks into `10_*` and `13_*`; keep legacy notebook as historical reference during transition |
| `notebooks/02_second_brick_openai_agents_adapter.ipynb` | OpenAI SDK adapter bridge and policy path explanation | Overlaps with `12_runtime_adapter_checks.ipynb` and parts of canonical idea validation | API key optional (some cells require key) | `merge` | Move adapter-focused checks to `12_*`; keep explanatory content in docs |
| `notebooks/03_third_brick_live_agent_tool_execution.ipynb` | Single-flow proof that eXo-brain intercepts and executes tools locally | Target canonical notebook behavior | API key required for live model turn | `keep` (as source), `promote` | Promote as canonical `01_idea_validation.ipynb` with one interaction workflow |

## Target Notebook Set

| Target Notebook | Purpose | Requirement |
|---|---|---|
| `notebooks/01_idea_validation.ipynb` | Canonical end-to-end deterministic tool-call proof (Notebook 3 style) | API key for live run; local smoke cell without key |
| `notebooks/10_core_orchestrator_checks.ipynb` | Focused checks for orchestrator event loop and deterministic executor path | No API key |
| `notebooks/11_policy_middleware_checks.ipynb` | `before_tool_call` / `after_tool_call` behavior verification | No API key |
| `notebooks/12_runtime_adapter_checks.ipynb` | Runtime adapter capability/health/session and turn event checks | No API key for stub path |
| `notebooks/13_tenant_and_limits_checks.ipynb` | Tenant quotas and rate-limit primitives validation | No API key |

## Notes

- Legacy brick notebooks remain in repo during this migration slice for rollback safety.
- Canonical references in docs should point only to the new notebook set.
