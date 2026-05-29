# eXo-brain Notebooks

Interactive notebooks for exploring, validating, and demonstrating eXo-brain's core modules.
They complement the automated test suite (`tests/`) — notebooks provide narrative context,
live outputs, and hands-on exploration that pytest tests do not.

**New here?** Start with `tutorial_01` → `tutorial_02` → `tutorial_03` → `tutorial_04` in order.
Each tutorial builds on the previous one. `tutorial_05`, `tutorial_06`, and `tutorial_07` are
standalone deep-dives you can run in any order after `tutorial_03`. **`tutorial_08`** is a
**governed-execution lab** (story + code): edit policy, ingress, and tool knobs, read stdout like
operator traces, and optionally run a **live** governed turn with `OPENAI_API_KEY`. The `check_` notebooks are
independent smoke tests you can run any time to confirm a module is working correctly.
The `edge_` notebooks explore boundary conditions and failure modes.

**Evaluator time-boxed paths:** [EVALUATOR_GUIDE.md](EVALUATOR_GUIDE.md) (15 min / 90 min / security / maintainer smoke).

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

**Kernel:** Use the project venv (`.venv` or `.exo_env`) — select a **Python 3.12** kernel whose
`sys.prefix` points at that environment before running any notebook.

```bash
# Activate the venv first (example: .venv)
source .venv/bin/activate

# Install the kernel if not already registered
python -m ipykernel install --user --name=exo-brain --display-name "eXo-brain (.venv)"

# Launch Jupyter
jupyter lab notebooks/
```

All notebooks run **top-to-bottom**. Cells marked `[REQUIRES API KEY]` skip automatically
when `OPENAI_API_KEY` is not set — everything else runs without a live API key.

---

## Build Scripts

Build scripts are the **source of truth** for notebook content. The `.ipynb` files on disk
are generated output — always edit the build script, then regenerate. Never edit `.ipynb` files directly.

| Script | Generates | Run command |
|---|---|---|
| `build_tutorials.py` | `tutorial_01_*` through `tutorial_08_*` | `python notebooks/build_tutorials.py` |
| `build_checks.py` | `check_01_*` through `check_04_*`, `edge_01_*`, `edge_02_*` | `python notebooks/build_checks.py` |

After regenerating, re-run the notebook cells to refresh outputs, then commit both
the `.py` script and the `.ipynb` file.

---

## Notebook Index

### Tutorials

Narrative walkthroughs in learning order. Run top-to-bottom. No API key required unless noted.

---

#### `tutorial_01_core_framework.ipynb`

**Purpose:** Understand how eXo-brain is structured and why it was built this way. Run a complete
orchestrated turn and a multi-node background job with full observability evidence.

**API key required:** No — everything runs in-process with in-memory adapters.

**What you will do inside:**
1. Register a tool in `ToolRegistry` with a risk tier and `is_state_changing=True`
2. Wire `Orchestrator` with `DeterministicFirstPolicyMiddleware` and `DeterministicToolExecutor`
3. Inject a `planned_tool_call` into a turn context and run it — watch the event stream
4. Understand each event: `TOOL_INTENT`, `TOOL_PROGRESS`, `OUTPUT_DELTA`, `RUN_COMPLETE`
5. Build a two-node DAG (`fetch → process`) with `BackgroundRuntime`
6. Inspect node outcomes, `RuntimeMetrics` counters, `RuntimeTimeline` event log, and structured logs

**Key insight:** The model emits intent. eXo-brain executes it — deterministically, with audit trail.

**Modules covered:** `src/core/orchestrator`, `src/core/background_runtime`, `src/core/scheduler`,
`src/core/task_graph`, `src/core/worker_pool`, `src/policies/middleware`, `src/tools/executor`,
`src/tools/registry`, `src/observability/*`

---

#### `tutorial_02_openai_adapter.ipynb`

**Purpose:** See exactly what eXo-brain adds on top of the OpenAI Agents SDK, starting from
real agent code exported by OpenAI Agent Builder.

**API key required:** Optional — 3 live cells require it; all other cells including the policy demo run without it.

**What you will do inside:**
1. Run the original agent with a `pass` tool body — observe the model hallucinating because it gets `None` back
2. Understand the **delegating wrapper** pattern: `@function_tool` body calls `executor.execute()` instead of doing work itself
3. Wire `calculate_result` into eXo-brain: real handler in `ToolRegistry`, policy + executor, delegating SDK wrapper
4. Run 3 live turns (add, multiply, subtract) and see `[eXo-brain] calculate_result(...) → {result}` in the output
5. Run a division-by-zero turn — see `ValueError` caught and returned as a structured error envelope
6. Run a HIGH-risk version of the same tool without an API key — confirms DETERMINISTIC mode is forced

**Key insight:** The `@function_tool` body is the integration seam. Everything else is already provider-neutral.

**Modules covered:** `src/runtime/openai_agents_runtime`, `src/runtime/runtime_adapter`,
`src/runtime/capability_map`, `src/core/orchestrator`, `src/policies/middleware`,
`src/tools/executor`, `src/tools/registry`, `src/schemas/events`, `src/schemas/tool_io`

---

#### `tutorial_03_bring_your_own_config.ipynb`

**Purpose:** Configure eXo-brain's ingress policy layer for your own deployment without touching
any framework code — choose your posture, write your rules, see live gate decisions.

**API key required:** No — fully deterministic, no model calls.

**What you will do inside:**
1. Compare `baseline` / `strict` / `hardened` ingress profiles side-by-side (char limits, blocked phrases)
2. Build a plain Python overlay dict — set profile, classifier mode/threshold/signals, and custom rules
3. Compile it into a live `IngressGateChain` with one function call
4. Run 10 representative prompts (normal, injection, competitor, legal, oversized) and see ALLOW/DENY/ESCALATE decisions
5. Switch the classifier from `shadow` (log only) to `enforce` (block) and observe the difference
6. Apply a packaged governance template (`data-perimeter-v1`), extend it with your own custom rules on top
7. Inspect `chain.policy_metadata()` — the structured governance audit payload logged at session start

**Key insight:** You only edit a Python dict. The gate chain recompiles from it. Nothing in the core changes.

**Modules covered:** `src/policies/ingress_gates`, `src/policies/ingress_profiles`, `src/policies/policy_templates`

---

#### `tutorial_04_audit_trail.ipynb`

**Purpose:** Understand how every tool call in eXo-brain produces a correlation-linked audit record,
and how the SHA-256 hash chain makes it cryptographically impossible to silently alter audit history.

**API key required:** No — fully deterministic, no model calls.

**What you will do inside:**
1. Wire `InMemoryAuditStore` + `ToolAuditPipeline` + `StructuredLogger` — the three components of the audit infrastructure
2. Execute a tool via `DeterministicToolExecutor` and capture `ToolResult.audit.correlation_id`
3. Emit a `tool.executed` audit event via `ToolAuditPipeline.emit()` and query it back from the store
4. Build a 3-record SHA-256 hash chain manually with `chain_record(payload, previous_hash)` — show `previous_hash → record_hash` links
5. Call `verify_chain(records)` → `True` — chain is intact
6. Mutate one record's payload and call `verify_chain` again → `False` — tamper detected
7. Serialize the chain and call `compute_audit_chain_fingerprint(records_as_dicts)` → `(chain_valid=True, last_hash)`

**Key insight:** Every tool call produces a correlation-linked audit record. The SHA-256 hash chain
makes it cryptographically impossible to silently alter audit history — any mutation is detected
immediately by `verify_chain`.

**Modules covered:** `src/audit/trail`, `src/persistence/audit_store`, `src/observability/tool_audit`,
`src/observability/logging`, `src/compliance/evidence_bundle`, `src/tools/executor`

---

#### `tutorial_05_multi_turn_sessions.ipynb`

**Purpose:** Understand how session state, conversation history, timeline correlation, and quota
enforcement work together across multiple turns of a conversation.

**API key required:** Optional — 1 live cell requires it; all structural cells run without it.

**What you will do inside:**
1. Wire `RuntimeTimeline` + `TenantQuotaManager` + `StructuredLogger` alongside the adapter
2. Build a minimal `SessionAdapter` that tracks conversation history per session in-memory
3. Simulate 3 turns — show history growing from 0 → 2 → 4 → 6 entries after each turn
4. Record timeline events with per-turn correlation IDs — call `timeline.entries_for(corr)` to retrieve per-turn traces
5. Call `quota_manager.check_submission(tenant_id, active_jobs=0)` → `QuotaDecision(allowed=True)`
6. Call `quota_manager.check_submission(tenant_id, active_jobs=2)` → `QuotaDecision(allowed=False, reason_code="TENANT_QUOTA_EXCEEDED")`
7. (Optional) Run 3 live conversation turns with the real OpenAI model — watch history grow after each turn

**Key insight:** Session state (conversation history) lives in the adapter layer. The `RuntimeTimeline`
links every event back to its session via correlation ID. Quota enforcement is stateless — the caller
tracks `active_jobs` and the manager decides allow/deny. Both work across any provider adapter.

**Modules covered:** `src/observability/timeline`, `src/tenancy/quotas`, `src/runtime/openai_agents_runtime`,
`src/observability/logging`, `src/observability/metrics`

---

#### `tutorial_06_background_workflows.ipynb`

**Purpose:** Learn how to run long-lived workflows as background DAG jobs with automatic retries,
structured failure outcomes, and checkpoint-based resume without re-executing completed nodes.

**API key required:** No — fully deterministic, no model calls.

**What you will do inside:**
1. Build a 4-node DAG (`fetch → validate → enrich → publish`) using `TaskGraph` and async `TaskNode` handlers
2. Wire `TaskScheduler` + `BackgroundRuntime` + `WorkerPool`, submit the job, and inspect all 4 `TaskOutcome` objects
3. Replace `validate` with a handler that raises `ValueError` — show `outcome.status == FAILED` and job halts
4. Use `TaskNode(retry_limit=2)` with a flaky handler (fails twice, succeeds third) — show `outcome.attempts == 3`
5. Pre-populate `InMemoryCheckpointStore` with `fetch` marked `COMPLETED`, then submit the job — the scheduler seeds the result with the checkpoint output and threads it into `validate`'s dependency map

**Key insight:** Failure is structured, not silent. Retries are declarative. Checkpoints enable resume
without re-executing completed nodes — which matters for expensive or side-effecting tasks.

**Modules covered:** `src/core/background_runtime`, `src/core/scheduler`, `src/core/task_graph`,
`src/core/checkpoint_store`, `src/core/worker_pool`, `src/persistence/contracts`,
`src/observability/logging`, `src/observability/metrics`, `src/observability/timeline`

---

#### `tutorial_07_governance_and_anomaly.ipynb`

**Purpose:** Understand the two independent governance layers in eXo-brain: advisory anomaly detection
(flags bad tenant metrics) and deterministic fair admission control (enforces concurrency fairness).

**API key required:** No — fully deterministic, no model calls.

**What you will do inside:**
1. Understand the BYOC governance model — what it means for multiple tenants to share infrastructure
2. Define metric snapshots for 3 tenants: `tenant-a` (healthy), `tenant-b` (healthy), `tenant-c` (anomalous)
3. Call `detect_governance_anomalies(...)` for each — empty list for a/b, 3 findings for c (`BYOC_COST_UTILIZATION_SPIKE`, `BYOC_REJECTION_RATE_SPIKE`, `BYOC_REJECTION_REASON_DOMINANCE`)
4. Wire `ByocFairAdmissionCoordinator(max_inflight_global=3)` — acquire 3 slots (all succeed), 4th times out → `None`
5. Inspect `coordinator.stats()` — show `fair_admission_inflight_total` and `fair_admission_pending_total`
6. Call `coordinator.release(token)` — slot becomes available; show next `acquire()` succeeds
7. Use `TenantPolicyOverlayStore` — set different overlays per tenant, retrieve and compare them

**Key insight:** Anomaly detection is advisory — it never blocks. Fair admission is deterministic —
it blocks when the global limit is hit. Both are independent of the ingress gate chain. Together they
give operators visibility and control over multi-tenant resource sharing.

**Modules covered:** `src/policies/governance_anomaly_detector`, `src/policies/byoc_fairness`,
`src/tenancy/policy_overlay`

---

#### `tutorial_08_governed_execution_sandbox.ipynb`

**Purpose:** **Story + code** governance lab — each part explains *why* a layer exists (ingress, policy,
deterministic tools, execution mode), what to edit, and how to read stdout. Opens with **For non-technical
readers** (executive path + jargon cheat sheet).

**Why this notebook exists (value prop):** LLMs can **guess** plausible answers. Governed execution means
**money-moving math and proofs** come from **your handler** behind policy + `DeterministicToolExecutor`, not
from model memory. The flagship demo is **`safe_add_proven`**: the model only supplies **`a`** and **`b`**;
the handler adds a **hidden `random_operand`** (per kernel) so **`sum = a + b + random_operand`**. Anyone
who answers plain **a+b** (e.g. **44** for 11+33) without the tool JSON did **not** use your trust boundary.
Part **4** prints the JSON locally and **`[PASS] Part 4 local proof`** when sum/token match the kernel.
Optional **Part 8** §3 runs **`[PASS]`/`[FAIL]`** verification against that same kernel (default **11+33**;
use **`NB_LIVE_MATH_A`/`B`** to match a **2+3** re-test), next to a raw **`sloppy_add_proven`** anti-example.

Optional **Part 8** also runs **governed vs raw** contrasts: ingress block, tenant **deny** on
`admin_reset`, the math proof above, and governed **`calculate_result`** multiply (Tutorial 02 contract) —
ingress runs first on the governed side.

**API key required:** **No** for Parts 1–7. **Part 8** uses `OPENAI_API_KEY` if set (otherwise prints skip).
**Part 8 cost controls:** `NB_LIVE_INGRESS`, `NB_LIVE_POLICY`, `NB_LIVE_MATH`, `NB_LIVE_CALC` (default on;
set to `0`/`false`/`off` to skip a block), plus optional `NB_LIVE_RAW_CALC_CONTRAST=1` for an extra raw
multiply bug demo.

**CI:** `architecture-fitness` runs `jupyter nbconvert --execute` on this notebook with an empty API key
(Part 8 skips live calls).

**Requires** `pip install -r requirements.txt` from repo root (editable `exo-brain-core-contracts` under
`packages/eXo_adapters/`). **`nest-asyncio`** is in `requirements.txt` for Jupyter when a loop is
already running (Parts 7–8).

**What you will do inside:**
1. Read the **beginner checklist**, **map**, and **deterministic vs provider-native** narrative, then bootstrap paths.
2. Tune `USER_RISK` → probe synthetic `SCENARIOS` twice (**strict vs relaxed** risk gates).
3. Set `USER_OVERLAY` → compare **global-only** vs **tenant overlay** on the same probe call.
4. Register `USER_TOOLS` → run **`safe_add_proven`** and read **`random_operand` / `sum` / `proof_token`** in stdout (three-operand proof); also **`calculate_result`** (Tutorial 02 parity).
5. Sweep `CAPABILITY_VARIANTS` → `select_execution_mode`.
6. Edit `INGRESS_OVERLAY` → `evaluate_prompt` / gate chain.
7. Stub orchestrator stream → `planned_tool_call` (no API key).
8. Optional live turn → real adapter + same registry/executor; ingress gate on user text first.

**Key insights:** (1) **`safe_add_proven`** — deterministic handler is the only source of the true sum and proof.
(2) Policy **escalate** / **deny** stop handler execution on the tool path; ingress **non-ALLOW** stops before
orchestration on the real API path — see `docs/architecture/governed-execution-pipeline.md` (**Hands-on proof** section).

**Modules covered:** `src/policies/risk_gates`, `src/policies/middleware`, `src/tenancy/policy_overlay`,
`src/tools/registry`, `src/tools/executor`, `src/observability/metrics`, `src/runtime/capability_map`,
`src/runtime/mode_selector`, `src/policies/ingress_gates`, `src/core/orchestrator`,
`src/runtime/openai_agents_runtime`

---

### Checks

Module smoke checks — deterministic, no API key, run top-to-bottom in under 5 seconds each.
Each check notebook includes **purpose, prerequisites, related tutorial, PASS criteria, and troubleshooting**
in the first markdown cell (enterprise-friendly packaging, not just internal asserts).

| File | What it checks | PASS condition |
|---|---|---|
| `check_01_core_orchestrator.ipynb` | `Orchestrator` routes a HIGH-risk state-changing tool call through the deterministic path | `RUN_COMPLETE` event received + `TOOL_PROGRESS` shows `state=completed` |
| `check_02_policy_middleware.ipynb` | `DeterministicFirstPolicyMiddleware` pre- and post-check paths | `before_tool_call` returns ALLOW for LOW-risk; `after_tool_call` returns `POLICY_POSTCHECK_FAILED` when success payload is missing |
| `check_03_runtime_adapter.ipynb` | `OpenAIAgentsRuntimeAdapter` session lifecycle and turn events | `healthcheck` returns healthy; `run_turn` with `planned_tool_call` emits `TOOL_INTENT` event |
| `check_04_tenant_and_limits.ipynb` | Quota and rate-limiter enforcement | `TenantQuotaManager` raises `TENANT_QUOTA_EXCEEDED`; in-memory and SQLite limiters both enforce sliding-window limits |

**Modules covered per check:**

- `check_01`: `src/core/orchestrator`, `src/policies/middleware`, `src/runtime/openai_agents_runtime`, `src/tools/executor`, `src/tools/registry`
- `check_02`: `src/policies/middleware`, `src/schemas/tool_io`
- `check_03`: `src/runtime/openai_agents_runtime`, `src/schemas/events`
- `check_04`: `src/tenancy/quotas`, `src/tenancy/rate_limiter`

---

### Edge Cases

Boundary condition and failure mode explorations. Fully deterministic — no API key, no external calls.
Run top-to-bottom. Each notebook targets a specific edge behavior and asserts it is correct.

---

#### `edge_01_ingress_policy_conflicts.ipynb`

**Purpose:** Prove that the ingress gate chain is deterministic when multiple gates could fire for
the same input — first non-ALLOW wins, always.

**API key required:** No — fully deterministic. Target runtime: under 3 minutes.

**What you will do inside:**
1. Configure an overlay where both the classifier (shadow mode) and a custom rule target the same phrase
2. Run the prompt — show `CustomRulesGate` fires (shadow classifier passes through; only custom rule denies)
3. Switch classifier to `enforce` mode — show `ClassifierHeuristicGate` fires first (it precedes `CustomRulesGate`)
4. Use a phrase that only a custom rule matches (classifier threshold too high) — show only `CustomRulesGate` fires
5. Use a prompt injection phrase also matched by a custom rule — show `PromptInjectionHeuristicGate` fires first (it precedes `CustomRulesGate`)
6. Run a clean prompt — confirm `ALLOW` is returned with no gate firing

**Key insight:** Gate ordering is fixed: `EmptyInput → MaxChars → ClassifierHeuristic → PromptInjectionHeuristic → CustomRules`.
First non-ALLOW wins. Shadow mode never blocks — it marks `classifier_shadow_triggered=True` and passes through.

**Modules covered:** `src/policies/ingress_gates`, `src/policies/ingress_profiles`

---

#### `edge_02_tool_error_envelopes.ipynb`

**Purpose:** Prove that `DeterministicToolExecutor` is a safety boundary — regardless of how a tool
fails, the model always receives a structured `ToolResult` envelope, never a raw exception.

**API key required:** No — fully deterministic. Target runtime: under 2 minutes.

**What you will do inside:**
1. Register 3 tools: one raises `ValueError`, one raises `RuntimeError`, one returns a valid `dict`
2. Execute the two failing tools through `executor.execute()` — assert `result.status == ToolStatus.ERROR` for both
3. Inspect `result.error` (`NormalizedError`) — show `code`, `category`, `message`, `retryable`; confirm `result.result is None`
4. Execute a tool that was never registered — show `error.code == "TOOL_NOT_FOUND"`
5. Execute the success tool — show `result.status == SUCCESS`, `result.result` populated, `audit.correlation_id` non-empty
6. Pass a `ToolCallContext` with `schema_version="0.9"` — show `error.code == "TOOL_CALL_VALIDATION_ERROR"` before the handler is even called

**Key insight:** The executor is a safety boundary — exceptions never leak to the model raw.
Every outcome is a typed `ToolResult` with `status`, `error`, and `audit` fields.

**Modules covered:** `src/tools/executor`, `src/tools/registry`, `src/schemas/tool_io`, `src/policies/middleware`

---

## Rules for Adding a New Notebook

1. Pick the right category: `tutorial_` / `check_` / `edge_`
2. Pick the next sequential number **in that category** (check existing files)
3. Name it: `<category>_<NN>_<slug>.ipynb`
4. Add a builder function to the matching build script (`build_tutorials.py` or `build_checks.py`)
5. Add a full entry to this README index — include purpose, API key requirement, and section-by-section breakdown
6. For `check_` notebooks: keep them deterministic, no API key, assert + print PASS
7. For `tutorial_` notebooks: narrative first — explain what and why before showing code
8. Commit the build script + notebook + README update together
