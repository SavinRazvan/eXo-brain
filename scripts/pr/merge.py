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
 - Call AFTER gh pr merge with --merge-sha <oid> so the artifact records the correct merge commit.
 - --branch is optional; if omitted the script reads the current git branch.
 - Checks for alignment artifact presence when --arch-impacting flag is set.
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def _head_sha() -> str:
    proc = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True)
    return proc.stdout.strip() or "unknown"


def _current_branch() -> str:
    proc = subprocess.run(
        ["git", "branch", "--show-current"], capture_output=True, text=True
    )
    return proc.stdout.strip() or "unknown"


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify merge readiness and emit merge artifact.")
    parser.add_argument("--pr", required=True, help="PR number or URL")
    parser.add_argument("--actor", required=True, help="Actor display name performing merge action")
    parser.add_argument(
        "--agents",
        required=True,
        help='Agent list, e.g. "review-pr | prepare-pr | merge-pr"',
    )
    parser.add_argument(
        "--merge-sha",
        default=None,
        help=(
            "Merge commit SHA from gh pr merge / gh pr view. "
            "Pass this after merge is complete so the artifact records the correct oid."
        ),
    )
    parser.add_argument(
        "--branch",
        default=None,
        help="Feature branch name (defaults to current git branch if omitted).",
    )
    parser.add_argument(
        "--arch-impacting",
        action="store_true",
        default=False,
        help="Set for architecture-impacting PRs; enforces alignment artifact presence check.",
    )
    args = parser.parse_args()

    local_dir = Path(".local")
    review_file = local_dir / "review.md"
    prep_file = local_dir / "prep.md"
    alignment_audit_file = local_dir / "alignment-audit.md"
    merge_file = local_dir / "merge.md"

    errors: list[str] = []
    if not review_file.exists():
        errors.append("missing .local/review.md")
    if not prep_file.exists():
        errors.append("missing .local/prep.md")
    if args.arch_impacting and not alignment_audit_file.exists():
        errors.append("missing .local/alignment-audit.md (required for architecture-impacting PRs)")

    if errors:
        for err in errors:
            print(f"[BLOCK] {err}")
        return 1

    branch = args.branch or _current_branch()
    merge_sha = args.merge_sha or _head_sha()
    sha_source = "provided" if args.merge_sha else "git HEAD (fallback — prefer passing --merge-sha)"

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
                f"- Branch: {branch}",
                "",
                "## Preconditions",
                f"- review artifact present: {review_file.exists()}",
                f"- prepare artifact present: {prep_file.exists()}",
                f"- alignment audit present: {alignment_audit_file.exists()}",
                "",
                "## Merge Summary",
                f"- merge SHA: {merge_sha} ({sha_source})",
                "- merge execution: completed via gh pr merge",
                "",
                "## Agent Notes",
                "- (agent: add merge method, checks used as evidence, and follow-up work items below)",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Created {merge_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
