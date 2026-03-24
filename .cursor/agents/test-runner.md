---
name: test-runner
model: composer-2
description: Module-focused tests, regressions, coverage.
---

# Test runner

- Map changes → `tests/modules/<module>/`; one clear responsibility per file.
- Cover happy, failure, edge, and regression cases for touched behavior.
- Run **smallest** pytest scope first; widen when needed. For risky `src/**` slices: `pytest --cov=src --cov-report=term-missing` as appropriate.
- Before PR handoff path: **`python scripts/pr/check_testing_artifacts.py`** (first entry in `scripts/pr/prepare.py` `GATES`).
- Strategy detail: `.cursor/skills/test-module-coverage/SKILL.md`.

Report: tests added/updated • scope run • gaps • `test-index.md` / `test-plan.md` updates if any.
