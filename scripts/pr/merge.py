"""
File: merge.py
Path: scripts/pr/merge.py
Role: Verifies merge prerequisites and writes merge summary artifact.
Used By:
 - .agents/skills/merge-pr/SKILL.md
Depends On:
 - argparse
 - pathlib
Notes:
 - This script does not perform git merge; it verifies readiness and logs evidence.
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def _head_sha() -> str:
    proc = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
    return proc.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify merge readiness and emit merge artifact.")
    parser.add_argument("--pr", required=True, help="PR number or URL")
    parser.add_argument("--actor", required=True, help="Actor display name performing merge action")
    parser.add_argument(
        "--agents",
        required=True,
        help='Agent list, e.g. "review-pr | prepare-pr | merge-pr"',
    )
    args = parser.parse_args()

    local_dir = Path(".local")
    review_file = local_dir / "review.md"
    prep_file = local_dir / "prep.md"
    merge_file = local_dir / "merge.md"

    if not review_file.exists() or not prep_file.exists():
        print("Missing required artifacts (.local/review.md and .local/prep.md).")
        return 1

    merge_file.write_text(
        "\n".join(
            [
                f"# Merge Artifact ({args.pr})",
                "",
                "## Attribution",
                f"- Action-By: {args.actor}",
                f"- Merged-By: {args.actor}",
                "- GitHub-User: @SavinRazvan",
                f"- Agent/s: {args.agents}",
                "",
                "## Preconditions",
                "- review artifact present: yes",
                "- prepare artifact present: yes",
                "",
                "## Merge Summary",
                f"- prepared head sha: {_head_sha()}",
                "- merge execution: perform via normal PR merge flow",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Created {merge_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
