# eXo-brain Notebooks

Interactive notebooks for exploring, validating, and demonstrating eXo-brain's core modules.
They complement the automated test suite (`tests/`) — notebooks provide narrative context,
live outputs, and hands-on exploration that pytest tests do not.

---

## Naming Standard

```
<category>_<NN>_<descriptive_slug>.ipynb
```

| Category prefix | Purpose |
|---|---|
| `tutorial_` | Narrative walkthrough teaching a concept end-to-end |
| `check_` | Module smoke check — proves a specific `src/` module works correctly |
| `edge_` | Edge case / failure / boundary condition exploration |

Rules:
- Numbers are sequential **within each category** (no cross-category collisions).
- Slugs are lowercase with underscores.
- Each notebook must be listed in this README index.
- Each notebook must have a corresponding builder function in the matching build script.
- Outputs may be committed when they serve as reference evidence (tutorials); clear them otherwise.

---

## How to Run

**Kernel:** `eXo-brain (.exo_env)` — select this kernel before running any notebook.

```bash
# Activate the venv first
source .exo_env/bin/activate

# Install the kernel if not already registered
python -m ipykernel install --user --name=exo-brain --display-name "eXo-brain (.exo_env)"

# Launch Jupyter
jupyter lab notebooks/
```

All notebooks run **top-to-bottom**. Cells marked `[REQUIRES API KEY]` skip automatically
when `OPENAI_API_KEY` is not set — everything else runs without a live API key.

---

## Build Scripts

Build scripts are the **source of truth** for notebook content. The `.ipynb` files on disk
are generated output — always edit the build script, then regenerate.

| Script | Generates | Run command |
|---|---|---|
| `build_tutorials.py` | `tutorial_01_*`, `tutorial_02_*` | `python notebooks/build_tutorials.py` |
| `build_checks.py` | `check_01_*` through `check_04_*` | `python notebooks/build_checks.py` |

After regenerating, re-run the notebook cells to refresh outputs, then commit both
the `.py` script and the `.ipynb` file.

---

## Notebook Index

### Tutorials

Narrative walkthroughs in learning order — no API key required unless noted.

| File | Purpose | API Key | src/ Modules Covered |
|---|---|---|---|
| `tutorial_01_core_framework.ipynb` | Core orchestration: deterministic tool call via in-process adapter + multi-node background DAG with full observability evidence | No | `src/core/orchestrator`, `src/core/background_runtime`, `src/core/scheduler`, `src/core/task_graph`, `src/core/worker_pool`, `src/policies/middleware`, `src/tools/executor`, `src/tools/registry`, `src/observability/*` |
| `tutorial_02_openai_adapter.ipynb` | OpenAI Agents SDK adapter story: original `pass` tool body → delegating wrapper pattern → live 3-turn run with `calculate_result` + policy demo without API key | Optional (3 cells) | `src/runtime/openai_agents_runtime`, `src/core/orchestrator`, `src/policies/middleware`, `src/tools/executor`, `src/tools/registry`, `src/schemas/events`, `src/schemas/tool_io` |

### Checks

Module smoke checks — deterministic, no API key, run top-to-bottom in under 5 seconds each.

| File | What it checks | src/ Modules Covered |
|---|---|---|
| `check_01_core_orchestrator.ipynb` | `Orchestrator` routes a HIGH-risk state-changing tool call through the deterministic path; asserts `RUN_COMPLETE` + `TOOL_PROGRESS` completed state in event stream | `src/core/orchestrator`, `src/policies/middleware`, `src/runtime/openai_agents_runtime`, `src/tools/executor`, `src/tools/registry` |
| `check_02_policy_middleware.ipynb` | `DeterministicFirstPolicyMiddleware`: `before_tool_call` allows LOW-risk call; `after_tool_call` catches missing success payload and returns `POLICY_POSTCHECK_FAILED` | `src/policies/middleware`, `src/schemas/tool_io` |
| `check_03_runtime_adapter.ipynb` | `OpenAIAgentsRuntimeAdapter`: session creation, `healthcheck`, `get_capabilities`, `run_turn` with `planned_tool_call` emits `TOOL_INTENT` event | `src/runtime/openai_agents_runtime`, `src/schemas/events` |
| `check_04_tenant_and_limits.ipynb` | `TenantQuotaManager` hard quota enforcement; in-memory `TenantRateLimiter` sliding window; SQLite-backed `SQLiteTenantRateLimiter` persistence | `src/tenancy/quotas`, `src/tenancy/rate_limiter` |

### Edge Cases

Reserved for boundary condition and failure mode exploration. Add here as needed.

| File | Purpose | src/ Modules Covered |
|---|---|---|
| *(none yet)* | | |

---

## Rules for Adding a New Notebook

1. Pick the right category: `tutorial_` / `check_` / `edge_`
2. Pick the next sequential number **in that category** (check existing files)
3. Name it: `<category>_<NN>_<slug>.ipynb`
4. Add a builder function to the matching build script (`build_tutorials.py` or `build_checks.py`)
5. Add it to the index table in this README
6. For `check_` notebooks: keep them deterministic, no API key, assert + print PASS
7. For `tutorial_` notebooks: narrative first — explain what and why before showing code
8. Commit the build script + notebook + README update together
