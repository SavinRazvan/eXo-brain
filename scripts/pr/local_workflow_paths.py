"""
File: local_workflow_paths.py
Path: scripts/pr/local_workflow_paths.py
Role: Canonical paths for PR workflow markdown under `.local/workflow-artifacts/`.
Used By:
 - scripts/pr/review.py
 - scripts/pr/prepare.py
 - scripts/pr/merge.py
Depends On:
 - pathlib
Notes:
 - Keep path strings aligned with `.cursor/rules/pr-workflow-enforcement.mdc` and
   `scripts/architecture/check_governance_consistency.py` merge.py parity fragments.
"""

from __future__ import annotations

from pathlib import Path

WORKFLOW_ARTIFACTS_DIR = Path(".local/workflow-artifacts")

REVIEW_MD = WORKFLOW_ARTIFACTS_DIR / "review.md"
PREP_MD = WORKFLOW_ARTIFACTS_DIR / "prep.md"
MERGE_MD = WORKFLOW_ARTIFACTS_DIR / "merge.md"
ALIGNMENT_AUDIT_MD = WORKFLOW_ARTIFACTS_DIR / "alignment-audit.md"
ALIGNMENT_TODOS_MD = WORKFLOW_ARTIFACTS_DIR / "alignment-todos.md"


def ensure_workflow_artifacts_dir() -> None:
    """Create `.local/workflow-artifacts` if missing."""
    WORKFLOW_ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
