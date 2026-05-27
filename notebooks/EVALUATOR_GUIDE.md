# eXo-brain Notebook Evaluator Guide

Quick paths for **technical evaluators**, **security reviewers**, and **design partners** exploring the repo on GitHub. Full index: [README.md](README.md).

**Runtime:** Python 3.12+, project `.venv`, `pip install -r requirements.txt` from repo root. Launch with `jupyter lab notebooks/`.

---

## 15-minute executive skim (no API key)

| Order | Notebook | Why |
|---|---|---|
| 1 | `tutorial_08` — read only **For non-technical readers** + **Map** | Business framing + stack map |
| 2 | `tutorial_03` — run ingress profile comparison cells | Config-driven governance without code changes |
| 3 | `edge_01` — Scenario 5 only | Clean ALLOW proof |

**You learn:** governance is layered (ingress → policy → deterministic tools), not a single filter.

---

## 90-minute technical evaluation (no API key)

| Order | Notebook | ~Time |
|---|---|---|
| 1 | `tutorial_01_core_framework.ipynb` | 30 min |
| 2 | `tutorial_03_bring_your_own_config.ipynb` | 20 min |
| 3 | `tutorial_04_audit_trail.ipynb` | 15 min |
| 4 | `edge_02_tool_error_envelopes.ipynb` | 10 min |
| 5 | `tutorial_08` Parts 1–7 | 25 min |

**Optional with API key:** `tutorial_02` live cells, `tutorial_08` Part 8 (set `NB_LIVE_*=0` to skip blocks).

---

## Security / governance focus

| Order | Notebook |
|---|---|
| 1 | `tutorial_03` |
| 2 | `edge_01` |
| 3 | `tutorial_04` |
| 4 | `tutorial_07` |
| 5 | `tutorial_08` |

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

Run top-to-bottom (~30 seconds total):

```
check_01 → check_02 → check_03 → check_04
```

Then if you touched ingress or tools:

```
edge_01 → edge_02
```

---

## What these notebooks are not

- Not a production deployment guide (see `MAINTAINER_STATUS.md`, `docker-compose.yml` is dev-only)
- Not a formal compliance certification pack
- Not a substitute for `pytest` (1200+ tests) — notebooks add **narrative evidence**

---

## Regenerating content

```bash
python notebooks/build_tutorials.py
python notebooks/build_checks.py
```

Standards: `docs/plans/notebook-standards.md`
