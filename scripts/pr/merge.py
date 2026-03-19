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


def _artifact_matches_pr(file_path: Path, pr_ref: str) -> tuple[bool, str]:
    if not file_path.exists():
        return False, f"missing {file_path}"
    first_line = ""
    try:
        content = file_path.read_text(encoding="utf-8")
        first_line = (content.splitlines()[0] if content else "").strip()
    except OSError as exc:
        return False, f"unable to read {file_path}: {exc}"

    if f"({pr_ref})" not in first_line:
        return False, (
            f"stale or mismatched artifact in {file_path}: "
            f"expected header containing ({pr_ref}), got: {first_line or '<empty>'}"
        )
    return True, "ok"


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
    parser.add_argument(
        "--check-only",
        action="store_true",
        default=False,
        help=(
            "Run prerequisite checks only and do not write .local/merge.md. "
            "Use this for pre-merge validation."
        ),
    )
    args = parser.parse_args()

    local_dir = Path(".local")
    review_file = local_dir / "review.md"
    prep_file = local_dir / "prep.md"
    alignment_audit_file = local_dir / "alignment-audit.md"
    alignment_todos_file = local_dir / "alignment-todos.md"
    merge_file = local_dir / "merge.md"

    errors: list[str] = []
    review_ok, review_detail = _artifact_matches_pr(review_file, args.pr)
    if not review_ok:
        errors.append(review_detail)

    prep_ok, prep_detail = _artifact_matches_pr(prep_file, args.pr)
    if not prep_ok:
        errors.append(prep_detail)

    if args.arch_impacting:
        if not alignment_audit_file.exists():
            errors.append(
                "missing .local/alignment-audit.md (required for architecture-impacting PRs)"
            )
        if not alignment_todos_file.exists():
            errors.append(
                "missing .local/alignment-todos.md (required for architecture-impacting PRs)"
            )

    if errors:
        for err in errors:
            print(f"[BLOCK] {err}")
        return 1

    if args.check_only:
        print("[PASS] merge precheck passed.")
        return 0

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
                f"- alignment todos present: {alignment_todos_file.exists()}",
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
