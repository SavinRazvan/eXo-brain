<!--
File: agent-workflow-procedures.md
Path: docs/operations/agent-workflow-procedures.md
Role: Canonical procedures for architecture-impacting audits (enterprise-auditor) and rules to avoid duplicating workflow text across README, rules, and skills.
Used By:
 - docs/operations/workflow-complete.md
 - Maintainers / agents updating governance or PR workflow docs
Depends On:
 - .cursor/agents/enterprise-auditor.md
 - .cursor/skills/enterprise-architecture-audit/SKILL.md
 - docs/roadmap/alignment-audit-schema.md
 - scripts/pr/prepare.py
Notes:
 - Do not copy long gate command lists into multiple files; reference `prepare.py` `GATES` and sync listed surfaces when commands change.
-->

# Agent workflow procedures (canonical)

## 1) Architecture-impacting advisory audit (alignment artifacts)

**When:** Module boundaries, runtime/policy workflow changes, test/CI path moves, roadmap/rule updates, or maintainer calls for alignment before prepare/merge.

**Canonical agent:** **`enterprise-auditor`** (`.cursor/agents/enterprise-auditor.md`) with **`.cursor/skills/enterprise-architecture-audit/SKILL.md`**.

**Procedure (advisory-only — no auto-fix in audit phase):**

1. Run a **focused alignment pass** (same skill; outputs limited to alignment files — see skill § “Focused alignment pass”) unless a **full** `enterprise-architecture-audit.md` is explicitly in scope.
2. Use **`docs/roadmap/alignment-audit-schema.md`** for severity and finding shape.
3. For deep module mapping first, use **`.cursor/skills/audit-module-map/SKILL.md`** under **`enterprise-auditor`** when topology/HTML export is needed.
4. Write merge-gate outputs only to:
   - **`.local/workflow-artifacts/alignment/alignment-audit.md`**
   - **`.local/workflow-artifacts/alignment/alignment-todos.md`**
5. Block **`/prepare-pr`** on open **`P0`** findings unless explicitly **accepted** with rationale (per maintainer policy); carry **`P1`/`P2`** in todos with owner/slice.

**Rule of law:** `.cursor/rules/advisory-audit-alignment-enforcement.mdc` + **`scripts/pr/merge.py --arch-impacting`** (presence of both alignment files).

**Deprecated:** `.agents/skills/audit-alignment/SKILL.md` is a redirect stub only.

---

## 2) Maintainer PR workflow (phases)

**Order:** `review-pr` → `prepare-pr` → `merge-pr` → post-merge **`finalize.py`**.

**Canonical narrative:** **`.agents/skills/PR_WORKFLOW.md`**  
**Executable stubs + gates:** **`scripts/pr/prepare.py`**, **`merge.py`**, **`review.py`**, **`finalize.py`**, **`verify_publish.py`**

**Checklist copy (non-authoritative):** **`workflow-complete.md`** — if it disagrees with `prepare.py` or `PR_WORKFLOW.md`, **fix the checklist**.

---

## 3) Merge / prepare gate commands — **single source of truth**

**Authoritative list:** `scripts/pr/prepare.py` → **`GATES`** (order matters).

As of last sync, that is:

1. `python scripts/pr/check_testing_artifacts.py`
2. `python -m pytest -q`
3. `python scripts/architecture/validate_layers.py`
4. `python scripts/architecture/scan_forbidden_imports.py`

**CI also runs** `python scripts/architecture/check_governance_consistency.py` (see `.github/workflows/architecture-fitness.yml`). Run it locally when changing governance, workflows, or tracked policy docs.

---

## 4) Anti-duplication rule (stop repeating the same list)

When **`GATES`** in `prepare.py` change, update **every** of these in the **same PR/slice** (or immediately after):

| Surface | Location |
|--------|-----------|
| Always-applied rule | `.cursor/rules/pr-workflow-enforcement.mdc` |
| Tracked onboarding doc | `README.md` § PR workflow + Quick start |
| Local agent manifest | `AGENTS.md` (if used) § Quality gates |
| Local planning | `.local/index-and-planning/current/plan.md` § Acceptance Gates |
| This checklist | `docs/operations/workflow-complete.md` § CI/prepare parity |
| Optional | `.agents/skills/prepare-pr/SKILL.md` / **`PR_WORKFLOW.md`** if they duplicate gate text |

**Do not** paste the full gate block into **`updates-log.md`** more than once per change; log **“gate list synced per agent-workflow-procedures §4”** and point to the commit or primary file.

---

## 5) After tracked documentation refreshes

If you change **README**, **workflow**, or **architecture** docs:

1. Run **`docs/operations/documentation-maintenance-checklist.md`** as applicable.
2. Append **one** concise entry to **`.local/index-and-planning/history/updates-log.md`** (what changed + pointer to canonical file).
3. If gates or audit policy changed, update **`.local/index-and-planning/audits/agent-governance-audit.md`** / **`agent-governance-todos.md`** only if findings status shifted — avoid narrative duplication.

---

## 6) Related planning files (roles)

| File | Role |
|------|------|
| `docs/operations/workflow-complete.md` | End-to-end maintainer steps |
| `.local/index-and-planning/audits/agent-governance-audit.md` | Advisory findings snapshot |
| `.local/index-and-planning/audits/agent-governance-todos.md` | Remediation backlog |
| `.local/index-and-planning/current/plan.md` / `work-tracker.md` | Slice + tasks |
| **`agent-workflow-procedures.md`** | **This file** — procedures + dedup contract |
