<!--
File: README.md
Path: configs/release/README.md
Role: Index of versioned release-gate configuration; links operator docs and git commit trailer policy.
Used By:
 - Maintainers editing thresholds under configs/release/
Depends On:
 - docs/operations/release-candidate-signoff-checklist.md
 - AGENTS.md
 - .cursor/rules/commit-trailer-format.mdc
Notes:
 - YAML/JSON here is machine policy for workflows; git commit text rules live in commit-trailer-format.mdc.
-->

# Release configuration (`configs/release/`)

Versioned **thresholds and rollout policy** consumed by release-candidate automation (see `.github/workflows/release-candidate.yml` and `docs/operations/release-candidate-signoff-checklist.md`).

| File | Role |
|------|------|
| `gate_thresholds.yaml` | Quality, security, reliability, governance, Option C pointers |
| `option_c_slo_thresholds.json` | SLO thresholds for Option C |
| `ingress_budget_thresholds.json` | Ingress budget limits |
| `rollout_policies.yaml` | Rollout strategy knobs |

## Operator docs

- `docs/operations/release-candidate-signoff-checklist.md` — `make rc-signoff`, CI, checklist
- `docs/releases/RELEASE_TEMPLATE.md` — release / rollout note template (when present)

## Git commits vs RC evidence

PRs that change these configs follow normal merge workflow. **Git** commit messages use **`.cursor/rules/commit-trailer-format.mdc`** (summary: **`AGENTS.md`** § Commits): required **`Author:`** / **`GitHub-User:`**, optional **`Assisted-by:`** when AI materially contributed — **no `Made-with:`** (redundant with `Author:`). **RC signoff outputs** (for example `.local/rc-signoff.md`) record signoff **runner** metadata separately.
