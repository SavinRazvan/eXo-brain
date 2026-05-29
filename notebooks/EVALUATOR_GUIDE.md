# eXo-brain Notebook Evaluator Guide

Quick paths for **technical evaluators**, **security reviewers**, and **design partners** exploring the repo on GitHub.

| Resource | Role |
|---|---|
| [README.md](README.md) | Full index (14 notebooks), prerequisites, per-notebook detail |
| [docs/plans/notebook-standards.md](../docs/plans/notebook-standards.md) | Regeneration contract, structure, CI |
| [docs/architecture/governed-execution-pipeline.md](../docs/architecture/governed-execution-pipeline.md) | Production turn ordering; **Hands-on proof** ↔ `tutorial_08` |

**Runtime:** Python 3.12+, project `.venv`, `pip install -r requirements.txt` from repo root. Launch: `jupyter lab notebooks/`. Use the venv-backed **`python3`** kernel (see README).

---

## Notebook inventory (14)

| ID | API key | Best for |
|---|---|---|
| `tutorial_01` | No | Core orchestration + background DAG |
| `tutorial_02` | Optional | OpenAI Agents SDK delegating wrapper |
| `tutorial_03` | No | Ingress / BYOC overlays |
| `tutorial_04` | No | Audit trail + hash chain |
| `tutorial_05` | Optional (Part 6) | Sessions, timeline, quotas |
| `tutorial_06` | No | Background DAG, retry, checkpoint |
| `tutorial_07` | No | Anomaly advisory + fair admission |
| `tutorial_08` | Part 8 only | Full governance lab + `safe_add_proven` proof |
| `check_01`–`check_04` | No | Maintainer smoke (~30 s total) |
| `edge_01`, `edge_02` | No | Ingress ordering + tool envelopes |

**Not a substitute for pytest:** the repo has **~1,200** automated tests under `tests/`; notebooks add **narrative and printable evidence**.

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

**Optional with API key:** `tutorial_02` `[REQUIRES API KEY]` cells; `tutorial_08` Part 8.

**Part 8 expectations (if you use a key):**

- **`§3 VERIFICATION (governed): PASS`** requires completed `tool_progress` **and** correct sum + `proof_token` in the governed reply.
- **`FAIL` on §2–§4 is common** when the model refuses tools — treat as diagnostic; Parts 1–7 are authoritative.
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
| 1 | `tutorial_03` |
| 2 | `edge_01` |
| 3 | `tutorial_04` |
| 4 | `tutorial_07` |
| 5 | `tutorial_08` (Parts 1–7 minimum; Part 8 optional) |

**Cross-read:** `docs/architecture/governed-execution-pipeline.md`

---

## OpenAI / Agents SDK integration focus

| Order | Notebook |
|---|---|
| 1 | `tutorial_02_openai_adapter.ipynb` |
| 2 | `tutorial_08` Part 8 (optional live) |
| 3 | `check_03_runtime_adapter.ipynb` |

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
```

Re-run affected notebooks to refresh committed outputs when you want evidence in the `.ipynb`.

---

## What these notebooks are not

- Not a production deployment guide (see `MAINTAINER_STATUS.md`; `docker-compose.yml` is dev-oriented)
- Not a formal compliance certification pack
- Not a replacement for CI (`architecture-fitness` runs full pytest + executes `tutorial_08` without a live key)

---

## Regenerating content

```bash
python notebooks/build_tutorials.py
python notebooks/build_checks.py
```

Standards and ownership map: `docs/plans/notebook-standards.md`
