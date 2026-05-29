<!--
File: alignment-audit-report-template.md
Path: docs/roadmap/alignment-audit-report-template.md
Role: Starter structure for .local/workflow-artifacts/alignment/alignment-audit.md.
Used By:
 - enterprise-auditor focused alignment passes
Depends On:
 - docs/roadmap/alignment-audit-schema.md
Notes:
 - Copy into .local/; add Action-By / GitHub-User per PR workflow conventions.
-->

# Alignment Audit Report

## Metadata
- Audit date:
- Scope:
- Auditor:
- Mode: advisory-only
- Reference schema: [alignment-audit-schema.md](alignment-audit-schema.md)

## Executive Summary
- Total findings:
- P0:
- P1:
- P2:
- Overall recommendation: `PROCEED` | `PROCEED WITH FIXES` | `HOLD`

## Findings By Severity

### P0
| ID | Category | Source | Target | Evidence | Recommendation | Status |
|---|---|---|---|---|---|---|
| | | | | | | |

### P1
| ID | Category | Source | Target | Evidence | Recommendation | Status |
|---|---|---|---|---|---|---|
| | | | | | | |

### P2
| ID | Category | Source | Target | Evidence | Recommendation | Status |
|---|---|---|---|---|---|---|
| | | | | | | |

## Module-by-Module Alignment
| Module Group | Roadmap / plans | Code / tests | Rules / skills | Result |
|---|---|---|---|---|
| core | | | | |
| runtime | | | | |
| tools | | | | |
| policies | | | | |
| api | | | | |
| tenancy | | | | |
| mcp | | | | |
| persistence | | | | |
| observability | | | | |
| security domain | | | | |
| audit / compliance | | | | |

## Accepted Divergences
| ID | Rationale | Owner | Review Date |
|---|---|---|---|
| | | | |

## Recommended Fix Sequence
1.
2.
3.

## Verification Notes
- PR prep gates (`scripts/pr/prepare.py` `GATES`): `check_testing_artifacts.py`, `pytest -q`, `validate_layers.py`, `scan_forbidden_imports.py`
- Governance doc changes: `python scripts/architecture/check_governance_consistency.py` when applicable
- CI workflow path consistency checked: yes / no
