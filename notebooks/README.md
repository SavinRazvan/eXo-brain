# eXo-brain Notebooks

Interactive notebooks for exploring, validating, and demonstrating eXo-brain's core modules.
They complement the automated test suite (`tests/`) with **narrative context plus assertion-backed
evidence**: committed cell outputs, explicit **`PASS`** lines, and exact checks on `ToolResult`
envelopes, policy decisions, and stream events.

**Why these exist for evaluators:** You can read or re-run notebooks to see **how the architecture
behaves**, not only that pytest passes. Tutorials tell the story; **`check_*`** and **`edge_*`**
notebooks are fast module proofs; **`tutorial_08`** is the **flagship local governed-execution lab**
(CI-executed on PRs). Optional **`tutorial_09`** adds live OpenAI contrasts when you have a key.

**Evidence model:** Content is generated from `build_tutorials.py` / `build_checks.py`. After edits,
maintainers re-execute notebooks and commit refreshed outputs so GitHub (or local Jupyter) shows
the same proofs reviewers would get from `nbconvert --execute`. Weak print-only cells are avoided —
PASS criteria are enforced with assertions that fail the notebook if behaviour drifts.

**New here?** Start with `tutorial_01` → `tutorial_02` → `tutorial_03` → `tutorial_04` in order.
Each tutorial builds on the previous one. `tutorial_05`, `tutorial_06`, and `tutorial_07` are
standalone deep-dives you can run in any order after `tutorial_03`. **`tutorial_08`** is the
**local governed-execution lab** (Parts 1–7, no API key). **`tutorial_09`** is the optional
**live** companion (ingress + governed contrasts with `OPENAI_API_KEY`). Run **`tutorial_08` first**;
**`tutorial_09`** continues in the same kernel (or uses a consolidated prereq cell). The split keeps
**`tutorial_08`** small enough for GitHub preview and CI (`nbconvert --execute` without a key). The `check_`
notebooks are independent smoke tests (~5 seconds each). The `edge_` notebooks are deterministic
boundary proofs.

**Evaluator time-boxed paths:** [EVALUATOR_GUIDE.md](EVALUATOR_GUIDE.md) (15 min / 90 min / security / maintainer smoke).

**Canonical standards:** [docs/plans/notebook-standards.md](../docs/plans/notebook-standards.md) (structure, regeneration, CI).

**Architecture (notebooks):** eXo-brain **core** (orchestrator, policy, tools, tenancy) runs against pluggable **runtime adapters** from PyPI. Notebooks use the shipped wheels via `src/*` shims — not in-tree `packages/`. Custom adapters implement the same `RuntimeAdapter` contract (`exo-brain-core-contracts`); see Tutorial 02 and `check_03`.

### Governed execution lab (`tutorial_08` → optional `tutorial_09`)

| Step | Notebook | API key | What you get |
|---|---|---|---|
| 1 | `tutorial_08_governed_execution_sandbox.ipynb` | No | Full local story: risk gates, tenant overlay, **`safe_add_proven`** three-operand proof, execution mode, ingress, stub **`planned_tool_call`** stream |
| 2 | `tutorial_09_governed_execution_live.ipynb` | Optional | Live **§1–§4** governed proofs + raw SDK contrasts; **§5** model-driven diagnostic (off by default); **§6** summary table |

Cross-read: [`docs/architecture/governed-execution-pipeline.md`](../docs/architecture/governed-execution-pipeline.md) (**Hands-on proof**).

---

## Inventory (15 notebooks)

| Notebook | Category | API key | Typical runtime |
|---|---|---|---|
| `tutorial_01_core_framework.ipynb` | tutorial | No | ~25 min |
| `tutorial_02_openai_adapter.ipynb` | tutorial | Optional (3 cells) | ~30 min |
| `tutorial_03_bring_your_own_config.ipynb` | tutorial | No | ~20 min |
| `tutorial_04_audit_trail.ipynb` | tutorial | No | ~15 min |
| `tutorial_05_multi_turn_sessions.ipynb` | tutorial | Optional (Part 6) | ~20 min |
| `tutorial_06_background_workflows.ipynb` | tutorial | No | ~20 min |
| `tutorial_07_governance_and_anomaly.ipynb` | tutorial | No | ~15 min |
| `tutorial_08_governed_execution_sandbox.ipynb` | tutorial | No (Parts 1–7) | ~10–20 min |
| `tutorial_09_governed_execution_live.ipynb` | tutorial | Optional (§1–§6; skip if unset) | ~10–15 min |
| `check_01_core_orchestrator.ipynb` | check | No | under 5 s |
| `check_02_policy_middleware.ipynb` | check | No | under 5 s |
| `check_03_runtime_adapter.ipynb` | check | No | under 5 s |
| `check_04_tenant_and_limits.ipynb` | check | No | under 5 s |
| `edge_01_ingress_policy_conflicts.ipynb` | edge | No | under 3 min |
| `edge_02_tool_error_envelopes.ipynb` | edge | No | under 2 min |

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
- Each notebook must be listed in this README index and have a builder in the matching build script.
- **Content source of truth:** `build_tutorials.py` / `build_checks.py` — regenerate `.ipynb` after edits.
- Outputs may be committed when they serve as **reference evidence** (tutorials, checks, edges); clear stale outputs before commit when content changed.
- **Assertion-backed:** Prefer exact assertions (`ToolResult` fields, policy `reason_code`, event order) over print-only “PASS” banners. Checks/edges must end with an explicit **PASS** line; tutorials use **`[PASS]`** / **`§N VERIFICATION (governed): PASS`** where applicable.

---

## How to Run

**Environment:** Python **3.12+**, project virtualenv (`.venv` recommended), dependencies from repo root:

```bash
pip install -r requirements.txt
```

**Kernel:** Select the Jupyter kernel backed by that venv. Generated notebooks use a portable kernelspec
(`display_name`: **Python 3 (eXo-brain venv)**, `name`: **`python3`**) — not a hardcoded `.exo_env` path.
Optional registration:

```bash
python -m ipykernel install --user --name=exo-brain --display-name "eXo-brain (.venv)"
```

**Launch:**

```bash
jupyter lab notebooks/
```

**Execution:** Run **top to bottom** the first time. Bootstrap cells add the repo root to `sys.path` (shared helpers in `notebook_common.py`).

Install deps from repo root:

```bash
pip install -r requirements.txt
```

This pulls all **four PyPI adapter wheels** (lockstep pin in `requirements.txt`):

| Distribution | Import | Role |
|---|---|---|
| `exo-brain-core-contracts` | `exo_brain_core_contracts` | `RuntimeAdapter` contract, events, tool I/O |
| `exo-brain-adapter-sdk` | `exo_brain_adapter_sdk` | Adapter authoring helpers |
| `exo-adapter-echo` | `exo_adapter_echo` | Deterministic reference adapter |
| `exo-adapter-openai` | `exo_adapter_openai` | OpenAI Agents SDK adapter |

Tutorials **01, 02, 05, 08, 09** and checks **01, 03** confirm PyPI adapter provenance at bootstrap (`<site-packages>/…` markers + module assert).

**API keys:** Cells marked **`[REQUIRES API KEY]`** (or **`tutorial_09`**) skip gracefully when
`OPENAI_API_KEY` is unset. Everything else is deterministic and needs no live provider.

---

## Build Scripts

| Script | Generates | Command |
|---|---|---|
| `notebook_common.py` | Shared bootstrap, wheel probe, kernelspec | Imported by builders (do not run directly) |
| `build_tutorials.py` | `tutorial_01_*` … `tutorial_09_*` | `python notebooks/build_tutorials.py` |
| `build_checks.py` | `check_01_*` … `check_04_*`, `edge_01_*`, `edge_02_*` | `python notebooks/build_checks.py` (`--execute` to refresh outputs) |

After regenerating, re-run notebook cells to refresh outputs, then commit the builder(s), `notebook_common.py` (if changed), and `.ipynb` together.

**CI:** In `.github/workflows/architecture-fitness.yml`, job **`automated_test_suite`** runs
`jupyter nbconvert --execute` on **`tutorial_08_governed_execution_sandbox.ipynb`** with
`OPENAI_API_KEY` empty (live cells in `tutorial_09` are not executed in CI). Triggered on PRs that touch `notebooks/**` (among other paths).

### GitHub in-browser preview

GitHub renders notebooks with **its own** nbformat/nbconvert stack. If you see
`An error occurred Using nbformat v5.10.4 and nbconvert v7.17.1`, that banner is **GitHub’s**
renderer failing — it is **not** fixed by changing `requirements.txt` (those pins are for local dev and CI only).

| Symptom | What to do |
|---------|------------|
| Generic render error on any `.ipynb` | Retry later; use [nbviewer](https://nbviewer.org/) or open locally with `.venv` |
| `tutorial_08` / `tutorial_09` slow or fail on GitHub preview | Run locally or use [nbviewer](https://nbviewer.org/) — split keeps `tutorial_08` CI-sized |
| Before push (metadata normalize) | `python scripts/dev/normalize_notebooks_for_github.py` |

Committed notebooks use **nbformat 4.4** (no cell ids) and portable kernelspec metadata for better GitHub compatibility.

---

## Notebook Index

### Tutorials

Narrative walkthroughs. Run top-to-bottom unless noted.

---

#### `tutorial_01_core_framework.ipynb`

**Purpose:** How eXo-brain is structured; run a single orchestrated turn and a two-node background DAG with observability.

**API key:** No — PyPI `OpenAIAgentsRuntimeAdapter` with `planned_tool_call` (no live model call).

**What you will do:**

1. Confirm four adapter wheels load (bootstrap probe)
2. Register a tool in `ToolRegistry` (HIGH risk, `is_state_changing=True`)
3. Wire `Orchestrator` with `DeterministicFirstPolicyMiddleware` and `DeterministicToolExecutor`
4. Inject `planned_tool_call` and stream events: `TOOL_PROGRESS`, `OUTPUT_DELTA`, `RUN_COMPLETE`
   (adapter emits `TOOL_INTENT` internally; orchestrator surfaces deterministic progress)
5. Build a `fetch → process` DAG with `BackgroundRuntime`; inspect outcomes, metrics, timeline, logs

**Key insight:** Model output is intent; eXo-brain executes deterministically with an audit trail. The adapter is real (PyPI); the turn is deterministic injection, not a live provider call.

**Modules:** `src/core/orchestrator`, `src/core/background_runtime`, `src/core/scheduler`, `src/core/task_graph`,
`src/core/worker_pool`, `src/policies/middleware`, `src/tools/executor`, `src/tools/registry`, `src/observability/*`,
`src/runtime/openai_agents_runtime` (shim → `exo-adapter-openai`)

**Related check:** `check_01_core_orchestrator.ipynb`

---

#### `tutorial_02_openai_adapter.ipynb`

**Title:** Tutorial 02 — **OpenAI Runtime Adapter** (filename slug: `openai_adapter`).

**Purpose:** What eXo-brain adds on top of the OpenAI Agents SDK — **delegating wrapper** pattern in Act 2, then the **production** path via PyPI `exo-adapter-openai` (`OpenAIAgentsRuntimeAdapter`).

**Teaching vs production:** Act 2 defines an inline `OpenAIAgentsSDKAdapter` class so the integration seam is visible in one notebook. Production code uses the shipped wheel (re-exported from `src/runtime/openai_agents_runtime`). Verify provenance in `check_03_runtime_adapter.ipynb`.

**API key:** Optional — **three** markdown sections marked `[REQUIRES API KEY]` (original `pass` tool demo;
three arithmetic live turns in one cell; division-by-zero observation). Policy demo and adapter wiring run without a key.

**What you will do:**

1. Run the original agent with `pass` tool body — model may guess when it receives `None`
2. Learn the **delegating wrapper**: `@function_tool` body calls `executor.execute()`
3. Wire `calculate_result` through registry, policy, executor, and SDK wrapper
4. Live turns: add, multiply, subtract — see `[eXo-brain] calculate_result(...) → {result}` in stdout
5. Live division-by-zero — **observe** model vs tool behaviour (not a formal envelope proof in this cell; see `edge_02` / Tutorial 04)
6. HIGH-risk `planned_tool_call` demo without API key — deterministic path forced (injected intent, not live model choice)

**Key insight:** The `@function_tool` body is the integration seam; orchestration stays provider-neutral. Shipped adapter: `exo-adapter-openai`; reference deterministic adapter: `exo-adapter-echo` (see `check_03`).

**Modules:** `src/runtime/openai_agents_runtime`, `src/runtime/runtime_adapter`, `src/runtime/capability_map`,
`src/core/orchestrator`, `src/policies/middleware`, `src/tools/executor`, `src/tools/registry`,
`src/schemas/events`, `src/schemas/tool_io`

**Related check:** `check_03_runtime_adapter.ipynb`

---

#### `tutorial_03_bring_your_own_config.ipynb`

**Purpose:** **Bring Your Own Configuration** — ingress and governance overlays via Python dicts. **Not** runtime adapter wiring (see Tutorial 02 / `check_03` for adapters).

**API key:** No.

**What you will do (Parts 1–7):**

1. Compare `baseline` / `strict` / `hardened` profiles (limits, blocked phrases)
2. Build and compile a Python overlay into `IngressGateChain`
3. Run **nine** representative prompts in Part 4 (normal, injection, competitor, legal, oversized)
4. Switch classifier `shadow` → `enforce` — Part 5 (enforce may **escalate**, not only deny)
5. Apply template `data-perimeter-v1` and extend with custom rules — Part 6
6. Inspect `chain.policy_metadata()` — Part 7

**Key insight:** Edit a dict; the gate chain recompiles. Core code stays unchanged. (Do not confuse with **BYOC** — Bring Your Own Compute — which is Tutorial 07.)

**Modules:** `src/policies/ingress_gates`, `src/policies/ingress_profiles`, `src/policies/policy_templates`

**Related edge:** `edge_01_ingress_policy_conflicts.ipynb`

---

#### `tutorial_04_audit_trail.ipynb`

**Purpose:** Correlation-linked audit records and SHA-256 hash-chain tamper detection.

**API key:** No.

**What you will do (Parts 1–7):** Wire `InMemoryAuditStore`, `ToolAuditPipeline`, `StructuredLogger`;
execute via `DeterministicToolExecutor`; emit and query events; build and verify a 3-record chain;
mutate a record and fail `verify_chain`; compute `compute_audit_chain_fingerprint`.

**Key insight:** Audit history is linked and tamper-evident.

**Modules:** `src/audit/trail`, `src/persistence/audit_store`, `src/observability/tool_audit`,
`src/observability/logging`, `src/compliance/evidence_bundle`, `src/tools/executor`

**Related edge:** `edge_02_tool_error_envelopes.ipynb`

---

#### `tutorial_05_multi_turn_sessions.ipynb`

**Purpose:** Session history, timeline correlation, and quota enforcement across turns.

**API key:** Optional — Part 6 live multi-turn only.

**What you will do:** Wire timeline + `TenantQuotaManager`; local **`SessionAdapter`** demo (Parts 2–3, key-free); simulate three turns
(history growth); per-turn `timeline.entries_for(corr)`; quota allow/deny with `TENANT_QUOTA_EXCEEDED`;
optional live turns with PyPI **`OpenAIAgentsRuntimeAdapter`** (Part 6: three turns on one `session_id`; cross-turn SDK memory and
tool proofs are **Tutorial 02** / **Tutorial 08**, not required here).

**Key insight:** Session state lives in the adapter layer; timeline and quotas are provider-agnostic. Part 2 uses a minimal inline adapter — not the Tutorial 02 educational `OpenAIAgentsSDKAdapter` class.

**Modules:** `src/observability/timeline`, `src/tenancy/quotas`, `src/runtime/openai_agents_runtime`,
`src/observability/logging`, `src/observability/metrics`

**Related check:** `check_04_tenant_and_limits.ipynb`

---

#### `tutorial_06_background_workflows.ipynb`

**Purpose:** Background DAG jobs with failure outcomes, retries, and checkpoint resume.

**API key:** No.

**What you will do (Parts 1–5):** Four-node DAG `fetch → validate → enrich → publish`; failure halts job;
`retry_limit=2` flaky node (`attempts == 3`); resume with `InMemoryCheckpointStore` seeding completed `fetch`.

**Key insight:** Failure is structured; checkpoints avoid redoing expensive nodes.

**Modules:** `src/core/background_runtime`, `src/core/scheduler`, `src/core/task_graph`,
`src/core/checkpoint_store`, `src/core/worker_pool`, `src/persistence/contracts`,
`src/observability/logging`, `src/observability/metrics`, `src/observability/timeline`

---

#### `tutorial_07_governance_and_anomaly.ipynb`

**Purpose:** **BYOC** (Bring Your Own Compute) — advisory anomaly detection vs deterministic process-local fair admission. Independent of ingress (Tutorial 03).

**API key:** No.

**What you will do (Parts 1–7, including 6b):**

1. Metric snapshots for `tenant-a` / `tenant-b` (healthy) and `tenant-c` (anomalous)
2. `detect_governance_anomalies` — tenant-c yields exactly **three** codes (asserted):
   `BYOC_COST_UTILIZATION_SPIKE`, `BYOC_REJECTION_RATE_SPIKE`, `BYOC_REJECTION_REASON_DOMINANCE`
3. `ByocFairAdmissionCoordinator(max_inflight_global=3)` — exact token/stat assertions; fourth `acquire` → `None`; `release` frees a slot
4. Part **6b** — background thread blocked in `acquire()` wakes on `release()` (`threading.Event` sync)
5. `TenantPolicyOverlayStore` — per-tenant overlays with retrieval + copy-isolation assertions

**Key insight:** Anomaly detection advises; fair admission enforces global inflight caps. Grant ordering under contention is covered by unit tests, not re-run here.

**Modules:** `src/policies/governance_anomaly_detector`, `src/policies/byoc_fairness`, `src/tenancy/policy_overlay`

---

#### `tutorial_08_governed_execution_sandbox.ipynb`

**Title:** Tutorial 08 — Governed execution: **local lab**.

**Purpose:** Story-driven **local** governance lab — ingress, risk policy, deterministic tools,
execution mode, stub orchestrator (Parts 1–7). No live OpenAI calls.

**API key:** **No.**

**What you will do:**

1. Bootstrap — repo path, `.env`, PyPI wheel provenance
2. **Parts 1–2** — `RiskGateConfig` knobs + synthetic `before_tool_call` probes
3. **Part 3** — tenant policy overlay (`DENY` vs `ESCALATE`)
4. **Part 4** — register tools, `run_tool`, divide-by-zero envelope, **`safe_add_proven`** kernel proof
5. **Part 5** — execution mode sweep (capability map + policy)
6. **Part 6** — ingress gate chain on representative prompts
7. **Checkpoint** — verify globals before orchestrator
8. **Part 7** — one-turn stub orchestrator with **`planned_tool_call`** (no API key)

**Flagship proof — `safe_add_proven`:** Model supplies `a` and `b`; handler adds hidden `random_operand`
per kernel → `sum` and `proof_token`. Plain **a+b** (e.g. 44 for 11+33) without tool JSON is **not** the trust boundary.

**Part 4:** `run_tool(...)` returns **`ToolResult`**; asserts exact success/error/blocked envelopes and metrics counters. Prints **`[PASS] Part 4 local proof`** when governed executor JSON matches the kernel baseline (not plain mental math).

**Part 7:** Stub orchestrator with **`CapturingOpenAIAgentsRuntimeAdapter`** — asserts event order, stream text, and submitted **`ToolResult`** fields (completed path + HIGH → **`POLICY_BLOCKED`**).

**Proof summary:** This notebook proves the **local governed execution path** (policy, deterministic tools, ingress, stub orchestrator) — not raw SDK comparison or model choice. Tutorial 09 covers optional live contrasts.

**Requires:** `pip install -r requirements.txt` (all four PyPI wheels). Bootstrap confirms PyPI provenance. **`nest-asyncio`** in requirements for Jupyter async in Part 7.

**Next step:** Optional live contrasts in **`tutorial_09_governed_execution_live.ipynb`** (same kernel recommended).

**Cross-read:** [`docs/architecture/governed-execution-pipeline.md`](../docs/architecture/governed-execution-pipeline.md) (**Hands-on proof** — local section)

**Modules:** `src/policies/risk_gates`, `src/policies/middleware`, `src/tenancy/policy_overlay`,
`src/tools/registry`, `src/tools/executor`, `src/observability/metrics`, `src/runtime/capability_map`,
`src/runtime/mode_selector`, `src/policies/ingress_gates`, `src/core/orchestrator`, `src/runtime/openai_agents_runtime`

---

#### `tutorial_09_governed_execution_live.ipynb`

**Title:** Tutorial 09 — Governed execution: **live contrasts**.

**Purpose:** Optional **live** governed vs **raw SDK** contrasts when **`OPENAI_API_KEY`** is set.
Governed **§2–§4** use **`planned_tool_call`** through `Orchestrator` (same reliable mechanism as tutorial_08 Part 7).

**API key:** **Optional** — cells skip with guidance when unset. Only post-setup cells may call OpenAI.

**Prerequisites:**

1. **Recommended:** Run **`tutorial_08`** top-to-bottom in this kernel, then continue here.
2. **Standalone:** Bootstrap + **consolidated prereq** cell (rebuilds tutorial_08 defaults).

**Cell flow:**

| Step | Section | Notes |
|---|---|---|
| Bootstrap | paths, wheels, `.env` | Same pattern as other tutorials |
| Consolidated prereq | skip if globals exist | Replays tutorial_08 Parts 1–4 + 6 defaults |
| Live setup | `HAS_OPENAI_KEY`, `NB_LIVE_*` flags | Prints flag matrix; skip live cells if no key |
| §1 | Ingress deny on secret pattern | Governed path stops pre-model (exact gate/reason asserted) |
| §2 | `admin_reset` policy block | **`tool_progress` `POLICY_BLOCKED`** + captured **`ToolResult`** (orchestrator consumes `TOOL_INTENT` internally) |
| §3 | `safe_add_proven` / `sloppy_add_proven` | **`§3 VERIFICATION (governed): PASS`** — completed tool + kernel sum/token in reply + submitted `ToolResult` |
| §4 | `calculate_result` multiply | Governed multiply + submitted product **391**; optional raw broken contrast |
| §5 | Model-driven diagnostic | **`NB_LIVE_MODEL_DRIVEN=1`** only; not used for §2–§4 PASS/FAIL |
| §6 | Live summary table | One line per section; **asserts no failures** among required §1–§4 when key present |

**Evidence:** Governed §1–§4 use **`CapturingGovernedLiveOpenAIAdapter`** (tenant_id injection on planned calls, submitted results captured). Raw SDK blocks are **observational** — API errors are non-fatal. Consolidated prereq asserts local **`admin_reset`** block via `run_tool` → **`ToolResult`**.

**Env controls (default on unless noted; set `0`/`false`/`off` to skip):**

| Variable | Default | Skips |
|---|---|---|
| `NB_LIVE_INGRESS` | on | §1 ingress + raw pair |
| `NB_LIVE_POLICY` | on | §2 `admin_reset` + raw pair |
| `NB_LIVE_MATH` | on | §3 `safe_add_proven` / `sloppy_add_proven` |
| `NB_LIVE_MATH_A` / `NB_LIVE_MATH_B` | 11 / 33 | §3 operands (match Part 4 kernel if re-testing 2+3) |
| `NB_LIVE_CALC` | on | §4 governed `calculate_result` multiply |
| `NB_LIVE_RAW_CALC_CONTRAST` | off | §4 optional raw broken multiply |
| `NB_LIVE_MODEL_DRIVEN` | off | §5 model-initiated diagnostic turns |

**Cross-read:** `docs/architecture/governed-execution-pipeline.md` (**Hands-on proof** — live section)

**Modules:** same governance stack as tutorial_08 (`src/core/orchestrator`, `src/policies/*`, `src/tools/*`, `src/runtime/openai_agents_runtime`)

### Checks

Fast module smoke checks. Each opens with **purpose, prerequisites, related tutorial, PASS means, troubleshooting**
(generated by `build_checks.py`).

| File | What it checks | PASS condition |
|---|---|---|
| `check_01_core_orchestrator.ipynb` | PyPI wheel probe + HIGH-risk `planned_tool_call` through orchestrator | Wheels load; progress `queued→running→completed`; `ToolResult` `SUCCESS` + `mode_used=DETERMINISTIC`; `PASS: orchestrator deterministic tool path` |
| `check_02_policy_middleware.ipynb` | `DeterministicFirstPolicyMiddleware` pre/post | `ALLOW` + `LOW_RISK_ALLOWED`; bad SUCCESS → `POLICY_POSTCHECK_FAILED`; expanded PASS line |
| `check_03_runtime_adapter.ipynb` | PyPI OpenAI + Echo adapters; health + planned tool intent | Wheels load; health `HEALTHY`; exact `TOOL_INTENT` fields match `planned_tool_call`; PASS line |
| `check_04_tenant_and_limits.ipynb` | Quota + fixed-window rate limiters | Hard/soft quota codes; exact remaining/retry; tenant + limiter isolation; PASS line |

---

### Edge Cases

Deterministic scenario notebooks. Final line: **`All edge_XX scenarios: PASS`**.

---

#### `edge_01_ingress_policy_conflicts.ipynb`

**Purpose:** First non-ALLOW wins when multiple gates could apply.

**API key:** No. Target: **under 3 minutes**.

**Scenarios (5):**

1. Shadow classifier + custom rule both match → `ingress-custom-rules` DENY (shadow does not block)
2. Enforce classifier → `ingress-classifier-heuristic` before custom rules
3. Custom rule only (classifier threshold too high)
4. Injection phrase + custom rule → `ingress-prompt-injection-heuristic` first
5. Clean prompt → ALLOW

**Gate order:** `EmptyInput → MaxChars → ClassifierHeuristic (or external routing) → PromptInjection → CustomRules → SignedPlugin`

**Modules:** `src/policies/ingress_gates`, `src/policies/ingress_profiles`

---

#### `edge_02_tool_error_envelopes.ipynb`

**Purpose:** `DeterministicToolExecutor` always returns typed `ToolResult` — no raw exceptions to the model.

**API key:** No. Target: **under 2 minutes**.

**Parts:**

| Part | Demonstrates |
|---|---|
| 1 | Register failing and success handlers |
| 2 | `ValueError` / `RuntimeError` → `ERROR` envelopes |
| 3 | `NormalizedError` fields; no stack in `result` |
| 4 | Unregistered tool → `TOOL_NOT_FOUND` |
| 5 | Success → `doubled=42`, `audit.correlation_id` |
| 6 | `schema_version="0.9"` → `TOOL_CALL_VALIDATION_ERROR` |

**Note:** `BLOCKED`, `TIMEOUT`, `CANCELLED` share the same shape but are covered in policy/orchestrator paths elsewhere.

**Modules:** `src/tools/executor`, `src/tools/registry`, `src/schemas/tool_io`, `src/policies/middleware`

---

## Rules for Adding a New Notebook

1. Pick category: `tutorial_` / `check_` / `edge_`
2. Next sequential number **in that category**
3. Name: `<category>_<NN>_<slug>.ipynb`
4. Add builder to `build_tutorials.py` or `build_checks.py` (reuse `notebook_common.py` for bootstrap/probes)
5. Update this README, `EVALUATOR_GUIDE.md` if evaluator-facing, and `docs/plans/notebook-standards.md` ownership table
6. **Checks/edges:** deterministic, assert + explicit PASS lines, no API key
7. **Tutorials:** story before code; skip guards for optional live sections (`tutorial_09`, `[REQUIRES API KEY]` cells)
8. Commit builder + `.ipynb` + doc updates together
