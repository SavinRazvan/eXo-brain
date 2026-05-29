<!--
File: exo_adapters_pypi_handoff-mission.md
Path: docs/archive/handoffs/exo_adapters_pypi_handoff-mission.md
Role: Archived mission playbook for spinning out eXo_adapters (superseded by completion status).
Used By:
 - docs/handoffs/exo_adapters_pypi_handoff.md
Depends On:
 - N/A (historical)
Notes:
 - Status: archived 2026-05-29. Mission completed; see docs/handoffs/exo_adapters_pypi_handoff.md and SavinRazvan/eXo_adapters.
-->

# [Archived] Handoff: publish **eXo_adapters** (GitHub + PyPI)

> **Archived:** 2026-05-29  
> **Canonical replacement:** [docs/handoffs/exo_adapters_pypi_handoff.md](../../handoffs/exo_adapters_pypi_handoff.md) (completion status), [SavinRazvan/eXo_adapters](https://github.com/SavinRazvan/eXo_adapters), [docs/operations/adapter-installation.md](../../operations/adapter-installation.md)  
> **Why archived:** Adapter packages live in the public **eXo_adapters** repo and on PyPI; eXo-brain pins them in `requirements.txt` / `requirements-adapters.txt` (no in-tree mirror). Do not run this mission again unless restarting extraction from scratch.

This file preserved the **pre-completion mission narrative** for traceability. For the full step-by-step checklist that used to live at `docs/handoffs/exo_adapters_pypi_handoff.md`, use **git history** on that path before the 2026-05-29 status rewrite.

**Summary of what the mission asked for (now done):**

- Create `SavinRazvan/eXo_adapters` with four packages under `packages/`.
- Publish `exo-brain-core-contracts`, `exo-brain-adapter-sdk`, `exo-adapter-echo`, `exo-adapter-openai` to PyPI.
- Wire eXo-brain to `pip install` those distributions (no mandatory local path hacks for operators).
- Keep provider SDKs behind adapter boundaries; no `src.*` imports inside adapter packages.
