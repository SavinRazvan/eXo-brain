---
name: review-pr
description: PR review phase — findings only, artifact stub + alignment when needed.
disable-model-invocation: true
---

# Review PR

**Goal:** Decide if the PR is ready for `/prepare-pr`.

## Steps

1. Read PR diff and context. **Do not** land code in this phase.
2. Focus: correctness, boundary violations (`src/runtime/*adapter*` SDK wall, core provider-neutrality), security, missing tests.
3. **Stub artifact:**  
   `python scripts/pr/review.py --pr <id|url> --actor "Savin I. Razvan" --agents "review-pr"`  
   Then **replace** `.local/workflow-artifacts/pr/review.md` with real findings and **READY FOR /prepare-pr** | **NEEDS WORK** | **NEEDS DISCUSSION**.
4. **Architecture-impacting:** write `.local/workflow-artifacts/alignment/alignment-audit.md` + `alignment-todos.md` per `docs/roadmap/alignment-audit-schema.md` (advisory only).

**More context:** `.agents/skills/PR_WORKFLOW.md`.
