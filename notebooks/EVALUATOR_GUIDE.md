# eXo-brain Notebook Evaluator Guide

Quick paths for **technical evaluators**, **security reviewers**, and **design partners** exploring the repo on GitHub.

| Resource | Role |
|---|---|
| [README.md](README.md) | Full index (14 notebooks), prerequisites, per-notebook detail |
| [docs/plans/notebook-standards.md](../docs/plans/notebook-standards.md) | Regeneration contract, structure, CI |
| [docs/architecture/governed-execution-pipeline.md](../docs/architecture/governed-execution-pipeline.md) | Production turn ordering; **Hands-on proof** ↔ `tutorial_08` |

**Runtime:** Python **3.12+**, project `.venv`, `pip install -r requirements.txt` from repo root. Launch: `jupyter lab notebooks/`. Use the venv-backed **`python3`** kernel (see README).

**Adapters (PyPI):** Install all four wheels from `requirements.txt` (`exo-brain-core-contracts`, `exo-brain-adapter-sdk`, `exo-adapter-echo`, `exo-adapter-openai`). Notebooks import via `src/*` shims or `exo_adapter_*` directly. Bootstrap cells in tutorials **01, 02, 05, 08** and checks **01, 03** print wheel paths to confirm PyPI provenance — not in-tree packages.

**Naming cheat sheet:**

| Term | Notebook | Meaning |
|---|---|---|
| **BYO configuration** | `tutorial_03` | Ingress / governance overlay dicts (no adapter code) |
| **BYOC** | `tutorial_07` | Bring Your Own Compute — anomaly + fair admission |
| **Runtime adapter** | `tutorial_02`, `check_03` | PyPI `exo-adapter-openai` + `exo-adapter-echo` |

---

## Notebook inventory (14)

| ID | API key | Best for |
|---|---|---|
| `tutorial_01` | No | Core orchestration + background DAG; PyPI adapter + `planned_tool_call` |
| `tutorial_02` | Optional | OpenAI runtime adapter — delegating wrapper (teaching) + PyPI `exo-adapter-openai` (production) |
| `tutorial_03` | No | Ingress / governance **configuration** overlays (not adapters) |
| `tutorial_04` | No | Audit trail + hash chain |
| `tutorial_05` | Optional (Part 6) | Sessions, timeline, quotas; Part 2 = local `SessionAdapter`; Part 6 = live PyPI adapter |
| `tutorial_06` | No | Background DAG, retry, checkpoint |
| `tutorial_07` | No | **BYOC** anomaly advisory + fair admission |
| `tutorial_08` | Part 8 only | Governance lab; Part 8 §1–§4 use `planned_tool_call` live proofs |
| `check_01`–`check_04` | No | Maintainer smoke (~30 s total); `check_01`/`check_03` verify PyPI wheels |
| `edge_01`, `edge_02` | No | Ingress ordering + tool envelopes |

**Not a substitute for pytest:** the repo has **~1,210** automated tests under `tests/` (plus 2 opt-in skipped: soak + live OpenAI); notebooks add **narrative and printable evidence**.

---

## 15-minute executive skim (no API key)

| Order | Notebook | Why |
|---|---|---|
| 1 | `tutorial_08` — **For non-technical readers** + **Map** only | Business framing + layer stack |
| 2 | `tutorial_03` — Part 4 prompt sweep | Config-driven ingress without code changes |
| 3 | `edge_01` — Scenario 5 | Clean ALLOW proof |

**You learn:** governance is layered (ingress → policy → deterministic tools), not one filter.

**Proof without a key:** In `tutorial_08` Part **4**, read **`safe_add_proven` JSON** — `sum` includes kernel-only **`random_operand`**. Plain **11+33=44** or **2+3=5** without that JSON means the model did not use your handler boundary.

---

## 90-minute technical evaluation (no API key)

| Order | Notebook | ~Time |
|---|---|---|
| 1 | `tutorial_01_core_framework.ipynb` | 30 min |
| 2 | `tutorial_03_bring_your_own_config.ipynb` | 20 min |
| 3 | `tutorial_04_audit_trail.ipynb` | 15 min |
| 4 | `edge_02_tool_error_envelopes.ipynb` | 10 min |
| 5 | `tutorial_08` Parts 1–7 (emphasize **Part 4**) | 25 min |

**Optional with API key:** `tutorial_02` `[REQUIRES API KEY]` cells; `tutorial_08` Part 8 (run **8.1**, then **§1–§4**).

**Part 8 expectations (if you use a key):**

- **§1–§4 governed proofs** use **`planned_tool_call`** through `Orchestrator` (same as Part 7) — not model-initiated tool choice.
- **`§N VERIFICATION (governed): PASS`** requires completed `tool_progress` (or ingress deny / `POLICY_BLOCKED` for §2) plus expected assistant text where applicable.
- **8.5** (`NB_LIVE_MODEL_DRIVEN=1`, off by default) explores model-initiated tools — often **no `TOOL_INTENT`** on the delegating path; treat as diagnostic only.
- Set `NB_LIVE_*=0` to skip blocks; align §3 operands with Part 4 via `NB_LIVE_MATH_A` / `NB_LIVE_MATH_B` when not using 11+33.

---

## Extended evaluation (+45 min, no API key)

| Notebook | ~Time | Focus |
|---|---|---|
| `tutorial_06_background_workflows.ipynb` | 20 min | DAG failure, retry, checkpoint |
| `tutorial_07_governance_and_anomaly.ipynb` | 15 min | BYOC anomaly + fair admission + Part 6b waiter |
| `edge_01_ingress_policy_conflicts.ipynb` | 10 min | First non-ALLOW gate ordering |

---

## Security / governance focus

| Order | Notebook |
|---|---|
| 1 | `tutorial_03` (ingress overlays) |
| 2 | `edge_01` |
| 3 | `tutorial_04` |
| 4 | `tutorial_07` (BYOC fairness / anomaly) |
| 5 | `tutorial_08` (Parts 1–7 minimum; Part 8 optional) |

**Cross-read:** `docs/architecture/governed-execution-pipeline.md`

---

## OpenAI / Agents SDK integration focus

| Order | Notebook | Notes |
|---|---|---|
| 1 | `tutorial_02_openai_adapter.ipynb` | Inline `OpenAIAgentsSDKAdapter` teaches the pattern; summary links to PyPI wheel |
| 2 | `check_03_runtime_adapter.ipynb` | Proves `exo-adapter-openai` + `exo-adapter-echo` load and healthcheck |
| 3 | `tutorial_08` Part 8 (optional live) | Governed `planned_tool_call` proofs |

**Bring your own adapter:** Implement `RuntimeAdapter` (`exo-brain-core-contracts`), pip-install your package, pass to `Orchestrator` or register via API `adapter_class_ref`. Notebooks default to shipped PyPI adapters.

---

## Maintainer smoke (after code changes)

Run top-to-bottom:

```
check_01 → check_02 → check_03 → check_04
```

If you touched ingress or tools:

```
edge_01 → edge_02
```

After editing notebook **content**, regenerate from builders (do not hand-edit JSON):

```bash
python notebooks/build_tutorials.py   # tutorials only
python notebooks/build_checks.py      # checks + edges
python notebooks/build_checks.py --execute   # regenerate + execute checks/edges (refreshes stdout evidence)
```

Shared bootstrap and wheel probes live in `notebooks/notebook_common.py`. Re-run affected notebooks to refresh committed outputs when you want evidence in the `.ipynb`.

---

## What these notebooks are not

- Not a production deployment guide (see `MAINTAINER_STATUS.md`; `docker-compose.yml` is dev-oriented)
- Not a formal compliance certification pack
- Not a replacement for CI (`architecture-fitness` runs full pytest with coverage floor + executes `tutorial_08` without a live key)

---

## Regenerating content

```bash
python notebooks/build_tutorials.py
python notebooks/build_checks.py          # add --execute to refresh check/edge outputs in one step
```

Standards and ownership map: `docs/plans/notebook-standards.md`
