<!--
File: notebook-standards.md
Path: docs/plans/notebook-standards.md
Role: Canonical contract for eXo-brain notebook categories, structure, and regeneration.
Used By:
 - Maintainers adding or editing notebooks
 - notebooks/README.md
Depends On:
 - notebooks/build_tutorials.py
 - notebooks/build_checks.py
 - notebooks/notebook_common.py
Notes:
 - Supersedes legacy names (01_idea_validation, 1x_*_checks).
-->

# Notebook standards

**Status:** active  
**Owner:** Maintainer (Savin I. Razvan)  
**Last reviewed:** 2026-05-29

Canonical index: **[notebooks/README.md](../../notebooks/README.md)** (15 notebooks).  
Evaluator paths: **[notebooks/EVALUATOR_GUIDE.md](../../notebooks/EVALUATOR_GUIDE.md)**.

## Categories (current)

| Prefix | Purpose | Audience |
|---|---|---|
| `tutorial_` | Narrative walkthrough; concepts before code | Evaluators, new contributors, design partners |
| `check_` | Fast module smoke (~5s); assert + PASS | Maintainers after refactors |
| `edge_` | Boundary / failure proofs; scenario-driven | Security, platform, compliance reviewers |

Naming: `<category>_<NN>_<slug>.ipynb` — numbers are sequential **within** each category.

## Source of truth

| Generates | Script |
|---|---|
| `tutorial_01` … `tutorial_09` | `python notebooks/build_tutorials.py` |
| `check_01` … `check_04`, `edge_01`, `edge_02` | `python notebooks/build_checks.py` |

**Do not hand-edit `.ipynb` files** for content changes — edit the build script, regenerate, re-run cells for outputs, commit both.

## Required structure — tutorials

1. **Title cell** — what it covers, API key policy, time estimate when relevant
2. **Bootstrap** — `.env` optional load, `sys.path`, `pip install -r requirements.txt` (four PyPI adapter wheels)
3. **Concept markdown** — architecture diagram or story before heavy code
4. **Section markdown** — numbered steps (“We will…”)
5. **Code + interpretation** — stdout is evidence
6. **`[REQUIRES API KEY]`** sections where live calls need a key (skip guards in code)
7. **Key insight / summary** — one paragraph takeaway
8. **Notebook navigation** footer (auto-appended by `build_tutorials.py`)

## Required structure — checks

1. **Header markdown** — category, purpose, prerequisites, related tutorial, modules, PASS means, troubleshooting
2. **Bootstrap code** — shared path setup
3. **Assert code** — prints `PASS: …` on success
4. No API key; deterministic only

## Required structure — edge cases

1. **Header** — purpose, prerequisites, related tutorial, modules, PASS means
2. **Scenario markdown → code** alternation
3. **Summary footer** — troubleshooting + link to tutorial

## Kernel and environment

- Use project **`.venv`** (Python **3.12+**)
- Kernelspec name: **`python3`** (portable; not a hardcoded `.exo_env` path)
- Install deps: `pip install -r requirements.txt` from repo root

## Expected output quality

- Assertions fail fast with clear messages (same spirit as [nbval](https://arxiv.org/abs/2001.04808): execute cells and treat outputs as tests)
- Checks and edges end with explicit **PASS** lines
- Tutorials use **`[PASS]`**, **`§N VERIFICATION (governed): PASS`**, or exact dict/`ToolResult` equality — not print-only banners
- API-key cells skip gracefully when `OPENAI_API_KEY` is unset; raw SDK contrast errors are non-fatal in **`tutorial_09`**
- Reason codes, gate IDs, and submitted tool envelopes asserted where the notebook claims proof
- Committed `.ipynb` outputs are **reference evidence** after maintainer re-execution

## CI

- Workflow: `.github/workflows/architecture-fitness.yml`, job **`automated_test_suite`**
- Command: `jupyter nbconvert --execute notebooks/tutorial_08_governed_execution_sandbox.ipynb` with `OPENAI_API_KEY` empty (local lab only; live cells are in `tutorial_09`)
- Trigger: PRs touching `notebooks/**` (among other paths in that workflow)
- Other notebooks: maintainer / evaluator runs locally (`check_*` + `edge_*` after ingress/tool changes)

## Evaluator entry point

See **`notebooks/EVALUATOR_GUIDE.md`** for 15 min / 90 min / extended / security / OpenAI-integration / maintainer smoke paths.

## Ownership map (logical)

| Notebook | Primary validation |
|---|---|
| `tutorial_01`, `check_01` | Core orchestration |
| `tutorial_02`, `check_03` | Runtime adapter (PyPI OpenAI + Echo) |
| `tutorial_03`, `edge_01` | Ingress policy |
| `tutorial_04`, `edge_02` | Audit / tool envelopes |
| `tutorial_05`, `check_04` | Tenancy / limits |
| `tutorial_06` | Background workflows |
| `tutorial_07` | Governance anomaly / fairness |
| `tutorial_08` | Local governed execution lab (Parts 1–7); **`safe_add_proven`** three-operand sum proof (see `governed-execution-pipeline.md` **Hands-on proof**) |
| `tutorial_09` | Optional live governed contrasts (§1–§6); requires `OPENAI_API_KEY` |
