"""
File: review.py
Path: scripts/pr/review.py
Role: Initializes local review artifact with attribution and branch stamp for PR review workflow.
Used By:
 - .agents/skills/review-pr/SKILL.md
Depends On:
 - argparse
 - pathlib
 - scripts/pr/local_workflow_paths.py
Notes:
 - Writes `.local/workflow-artifacts/review.md` with the attribution block only (PR number, actor, branch, agents).
 - The agent MUST overwrite this file with actual review findings and recommendation.
 - Script does not run on existing files if --no-overwrite is passed (safe re-init guard).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

_PR_DIR = Path(__file__).resolve().parent
if str(_PR_DIR) not in sys.path:
    sys.path.insert(0, str(_PR_DIR))

from local_workflow_paths import REVIEW_MD, ensure_workflow_artifacts_dir


def _current_branch() -> str:
    proc = subprocess.run(
        ["git", "branch", "--show-current"], capture_output=True, text=True
    )
    return proc.stdout.strip() or "unknown"


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize PR review artifact.")
    parser.add_argument("--pr", required=True, help="PR number or URL")
    parser.add_argument("--actor", required=True, help="Actor display name performing review action")
    parser.add_argument(
        "--agents",
        required=True,
        help='Agent list, e.g. "review-pr | prepare-pr | merge-pr"',
    )
    parser.add_argument(
        "--no-overwrite",
        action="store_true",
        default=False,
        help="Skip writing if workflow review.md already exists (safe re-init guard).",
    )
    args = parser.parse_args()

    ensure_workflow_artifacts_dir()
    review_file = REVIEW_MD

    if args.no_overwrite and review_file.exists():
        print(f"Skipped (already exists): {review_file}")
        return 0

    branch = _current_branch()

    review_file.write_text(
        "\n".join(
            [
                f"# Review Artifact ({args.pr})",
                "",
                "## Attribution",
                f"- Action-By: {args.actor}",
                f"- Reviewed-By: {args.actor}",
                "- GitHub-User: @SavinRazvan",
                f"- Agent/s: {args.agents}",
                f"- Branch: {branch}",
                "",
                "## Findings",
                "- (agent: replace this stub with actual review findings)",
                "",
                "## Recommendation",
                "- (agent: replace with READY FOR /prepare-pr | NEEDS WORK | NEEDS DISCUSSION)",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Created {review_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
