"""
File: review.py
Path: scripts/pr/review.py
Role: Initializes local review artifact for PR review workflow.
Used By:
 - .agents/skills/review-pr/SKILL.md
Depends On:
 - argparse
 - pathlib
Notes:
 - Writes .local/review.md as a deterministic handoff artifact.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize PR review artifact.")
    parser.add_argument("--pr", required=True, help="PR number or URL")
    parser.add_argument("--actor", required=True, help="Actor display name performing review action")
    args = parser.parse_args()

    local_dir = Path(".local")
    local_dir.mkdir(exist_ok=True)
    review_file = local_dir / "review.md"
    review_file.write_text(
        "\n".join(
            [
                f"# Review Artifact ({args.pr})",
                "",
                "## Attribution",
                f"- Action-By: {args.actor}",
                f"- Reviewed-By: {args.actor}",
                "- GitHub-User: @SavinRazvan",
                "",
                "## Findings",
                "- Add findings here",
                "",
                "## Recommendation",
                "- READY FOR /prepare-pr | NEEDS WORK | NEEDS DISCUSSION",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Created {review_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
