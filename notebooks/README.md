# eXo-brain Notebooks

Interactive notebooks for exploring, validating, and demonstrating eXo-brain's core modules.
They complement the automated test suite (`tests/`) — notebooks provide narrative context,
live outputs, and hands-on exploration that pytest does not.

**New here?** Start with `tutorial_01` → `tutorial_02` → `tutorial_03` → `tutorial_04` in order.
Each tutorial builds on the previous one. `tutorial_05`, `tutorial_06`, and `tutorial_07` are
standalone deep-dives you can run in any order after `tutorial_03`. **`tutorial_08`** is a
**governed-execution lab** (story + code): edit policy, ingress, and tool knobs, read stdout like
operator traces, and optionally run **live** governed contrasts with `OPENAI_API_KEY`. The `check_`
notebooks are independent smoke tests (~5 seconds each). The `edge_` notebooks are deterministic
boundary proofs.

**Evaluator time-boxed paths:** [EVALUATOR_GUIDE.md](EVALUATOR_GUIDE.md) (15 min / 90 min / security / maintainer smoke).

**Canonical standards:** [docs/plans/notebook-standards.md](../docs/plans/notebook-standards.md) (structure, regeneration, CI).

---

## Inventory (14 notebooks)

| Notebook | Category | API key | Typical runtime |
|---|---|---|---|
| `tutorial_01_core_framework.ipynb` | tutorial | No | ~25 min |
| `tutorial_02_openai_adapter.ipynb` | tutorial | Optional (3 cells) | ~30 min |
| `tutorial_03_bring_your_own_config.ipynb` | tutorial | No | ~20 min |
| `tutorial_04_audit_trail.ipynb` | tutorial | No | ~15 min |
| `tutorial_05_multi_turn_sessions.ipynb` | tutorial | Optional (Part 6) | ~20 min |
| `tutorial_06_background_workflows.ipynb` | tutorial | No | ~20 min |
| `tutorial_07_governance_and_anomaly.ipynb` | tutorial | No | ~15 min |
| `tutorial_08_governed_execution_sandbox.ipynb` | tutorial | No (Parts 1–7); Part 8 optional | ~15–25 min |
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
- Outputs may be committed when they serve as reference evidence (tutorials); clear stale outputs before commit when content changed.

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

**Execution:** Run **top to bottom** the first time. Bootstrap cells add the repo root and, when present,
`packages/eXo_adapters/packages/exo-brain-core-contracts/src` to `sys.path`.

**API keys:** Cells marked **`[REQUIRES API KEY]`** (or tutorial Part 8) skip gracefully when
`OPENAI_API_KEY` is unset. Everything else is deterministic and needs no live provider.

---

## Build Scripts

| Script | Generates | Command |
|---|---|---|
| `build_tutorials.py` | `tutorial_01_*` … `tutorial_08_*` | `python notebooks/build_tutorials.py` |
| `build_checks.py` | `check_01_*` … `check_04_*`, `edge_01_*`, `edge_02_*` | `python notebooks/build_checks.py` (`--execute` to refresh outputs) |

After regenerating, re-run notebook cells to refresh outputs, then commit the `.py` builder and `.ipynb` together.

**CI:** In `.github/workflows/architecture-fitness.yml`, job **`automated_test_suite`** runs
`jupyter nbconvert --execute` on **`tutorial_08_governed_execution_sandbox.ipynb`** with
`OPENAI_API_KEY` empty (Part 8 skips live calls). Triggered on PRs that touch `notebooks/**` (among other paths).

---

## Notebook Index

### Tutorials

Narrative walkthroughs. Run top-to-bottom unless noted.

---

#### `tutorial_01_core_framework.ipynb`

**Purpose:** How eXo-brain is structured; run a single orchestrated turn and a two-node background DAG with observability.

**API key:** No — in-process adapters only.

**What you will do:**

1. Register a tool in `ToolRegistry` (HIGH risk, `is_state_changing=True`)
2. Wire `Orchestrator` with `DeterministicFirstPolicyMiddleware` and `DeterministicToolExecutor`
3. Inject `planned_tool_call` and stream events: `TOOL_INTENT`, `TOOL_PROGRESS`, `OUTPUT_DELTA`, `RUN_COMPLETE`
4. Build a `fetch → process` DAG with `BackgroundRuntime`; inspect outcomes, metrics, timeline, logs

**Key insight:** Model output is intent; eXo-brain executes deterministically with an audit trail.

**Modules:** `src/core/orchestrator`, `src/core/background_runtime`, `src/core/scheduler`, `src/core/task_graph`,
`src/core/worker_pool`, `src/policies/middleware`, `src/tools/executor`, `src/tools/registry`, `src/observability/*`

---

#### `tutorial_02_openai_adapter.ipynb`

**Purpose:** What eXo-brain adds on top of the OpenAI Agents SDK, starting from Agent Builder–style agent code.

**API key:** Optional — **three** markdown sections marked `[REQUIRES API KEY]` (original `pass` tool demo;
three arithmetic live turns in one cell; division-by-zero observation). Policy demo and adapter wiring run without a key.

**What you will do:**

1. Run the original agent with `pass` tool body — model may guess when it receives `None`
2. Learn the **delegating wrapper**: `@function_tool` body calls `executor.execute()`
3. Wire `calculate_result` through registry, policy, executor, and SDK wrapper
4. Live turns: add, multiply, subtract — see `[eXo-brain] calculate_result(...) → {result}` in stdout
5. Live division-by-zero — **observe** model vs tool behaviour (not a formal envelope proof in this cell; see `edge_02` / Tutorial 04)
6. HIGH-risk `planned_tool_call` demo without API key — deterministic path forced (injected intent, not live model choice)

**Key insight:** The `@function_tool` body is the integration seam; orchestration stays provider-neutral.

**Modules:** `src/runtime/openai_agents_runtime`, `src/runtime/runtime_adapter`, `src/runtime/capability_map`,
`src/core/orchestrator`, `src/policies/middleware`, `src/tools/executor`, `src/tools/registry`,
`src/schemas/events`, `src/schemas/tool_io`

**Related check:** `check_03_runtime_adapter.ipynb`

---

#### `tutorial_03_bring_your_own_config.ipynb`

**Purpose:** Configure ingress policy via overlay dicts — no framework code changes.

**API key:** No.

**What you will do (Parts 1–7):**

1. Compare `baseline` / `strict` / `hardened` profiles (limits, blocked phrases)
2. Build and compile a Python overlay into `IngressGateChain`
3. Run **nine** representative prompts in Part 4 (normal, injection, competitor, legal, oversized)
4. Switch classifier `shadow` → `enforce` — Part 5 (enforce may **escalate**, not only deny)
5. Apply template `data-perimeter-v1` and extend with custom rules — Part 6
6. Inspect `chain.policy_metadata()` — Part 7

**Key insight:** Edit a dict; the gate chain recompiles. Core code stays unchanged.

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

**What you will do:** Wire timeline + `TenantQuotaManager`; session-aware adapter; simulate three turns
(history growth); per-turn `timeline.entries_for(corr)`; quota allow/deny with `TENANT_QUOTA_EXCEEDED`;
optional live OpenAI conversation (Part 6: three turns on one `session_id`; cross-turn SDK memory and
tool proofs are **Tutorial 02** / **Tutorial 08**, not required here).

**Key insight:** Session state lives in the adapter; timeline and quotas are provider-agnostic.

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

**Purpose:** Advisory anomaly detection vs deterministic fair admission (independent of ingress).

**API key:** No.

**What you will do (Parts 1–7, including 6b):**

1. Metric snapshots for `tenant-a` / `tenant-b` (healthy) and `tenant-c` (anomalous)
2. `detect_governance_anomalies` — tenant-c typically yields **three** codes:
   `BYOC_COST_UTILIZATION_SPIKE`, `BYOC_REJECTION_RATE_SPIKE`, `BYOC_REJECTION_REASON_DOMINANCE`
3. `ByocFairAdmissionCoordinator(max_inflight_global=3)` — fourth `acquire` → `None`; `release` frees a slot
4. Part **6b** — background thread blocked in `acquire()` wakes on `release()`
5. `TenantPolicyOverlayStore` — per-tenant overlays

**Key insight:** Anomaly detection advises; fair admission enforces global inflight caps.

**Modules:** `src/policies/governance_anomaly_detector`, `src/policies/byoc_fairness`, `src/tenancy/policy_overlay`

---

#### `tutorial_08_governed_execution_sandbox.ipynb`

**Purpose:** Story-driven governance lab — ingress, risk policy, deterministic tools, execution mode,
stub orchestrator, optional live contrasts.

**API key:** **No** for Parts 1–7. **Part 8** optional when `OPENAI_API_KEY` is set (otherwise skip text).

**Flagship proof — `safe_add_proven`:** Model supplies `a` and `b`; handler adds hidden `random_operand`
per kernel → `sum` and `proof_token`. Plain **a+b** (e.g. 44 for 11+33) without tool JSON is **not** the trust boundary.

**Part 4:** Prints handler JSON and **`[PASS] Part 4 local proof`** when sum/token match the kernel.

**Part 8 (optional live):** Run **8.1 setup**, then **§1–§4** cells. Governed proofs use **`planned_tool_call`**
(same mechanism as Part 7) — §2–§4 do **not** depend on the model choosing tools. **8.5** (`NB_LIVE_MODEL_DRIVEN=1`,
off by default) is model-driven diagnostic only; **8.6** prints the live summary table.

**Part 8 env controls (default on unless noted; set `0`/`false`/`off` to skip):**

| Variable | Default | Skips |
|---|---|---|
| `NB_LIVE_INGRESS` | on | §1 ingress + raw pair |
| `NB_LIVE_POLICY` | on | §2 `admin_reset` + raw pair |
| `NB_LIVE_MATH` | on | §3 `safe_add_proven` / `sloppy_add_proven` |
| `NB_LIVE_MATH_A` / `NB_LIVE_MATH_B` | 11 / 33 | §3 operands (match Part 4 kernel if re-testing 2+3) |
| `NB_LIVE_CALC` | on | §4 governed `calculate_result` multiply |
| `NB_LIVE_RAW_CALC_CONTRAST` | off | §4 optional raw broken multiply |
| `NB_LIVE_MODEL_DRIVEN` | off | §8.5 model-initiated diagnostic turns |

**Requires:** `pip install -r requirements.txt` (contracts under `packages/eXo_adapters/…` or editable install).
**`nest-asyncio`** in requirements for Jupyter async in Parts 7–8.

**Parts map:** 1–2 risk + scenarios; 3 tenant overlay; 4 tools; 5 execution mode; 6 ingress; 7 stub orchestrator;
8 optional live (8.1 setup → §1–§4 `planned_tool_call` proofs → optional 8.5 model-driven → 8.6 summary).

**Cross-read:** `docs/architecture/governed-execution-pipeline.md` (**Hands-on proof**)

**Modules:** `src/policies/risk_gates`, `src/policies/middleware`, `src/tenancy/policy_overlay`,
`src/tools/registry`, `src/tools/executor`, `src/observability/metrics`, `src/runtime/capability_map`,
`src/runtime/mode_selector`, `src/policies/ingress_gates`, `src/core/orchestrator`, `src/runtime/openai_agents_runtime`

---

### Checks

Fast module smoke checks. Each opens with **purpose, prerequisites, related tutorial, PASS means, troubleshooting**
(generated by `build_checks.py`).

| File | What it checks | PASS condition |
|---|---|---|
| `check_01_core_orchestrator.ipynb` | HIGH-risk state-changing `planned_tool_call` through orchestrator | `run_complete` + `tool_progress` `state=completed`; `PASS: orchestrator deterministic tool path` |
| `check_02_policy_middleware.ipynb` | `DeterministicFirstPolicyMiddleware` pre/post | `before_tool_call` allow; bad SUCCESS → `POLICY_POSTCHECK_FAILED`; `PASS: policy middleware checks` |
| `check_03_runtime_adapter.ipynb` | `OpenAIAgentsRuntimeAdapter` health + planned tool intent | Healthy healthcheck + `tool_intent`; `PASS: runtime adapter planned tool-intent path` |
| `check_04_tenant_and_limits.ipynb` | Quota + in-memory and SQLite rate limiters | `TENANT_QUOTA_EXCEEDED`; in-memory blocks 3rd request, SQLite (max=1) blocks 2nd; `PASS: tenancy and limits checks` |

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

**Gate order:** `EmptyInput → MaxChars → ClassifierHeuristic → PromptInjectionHeuristic → CustomRules`

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
4. Add builder to `build_tutorials.py` or `build_checks.py`
5. Update this README, `EVALUATOR_GUIDE.md` if evaluator-facing, and `docs/plans/notebook-standards.md` ownership table
6. **Checks/edges:** deterministic, assert + explicit PASS lines, no API key
7. **Tutorials:** story before code; skip guards for optional live sections
8. Commit builder + `.ipynb` + doc updates together
