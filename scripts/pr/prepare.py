"""
File: prepare.py
Path: scripts/pr/prepare.py
Role: Runs preparation gates and emits local prepare artifact.
Used By:
 - .agents/skills/prepare-pr/SKILL.md
Depends On:
 - argparse
 - pathlib
 - subprocess
 - scripts/pr/local_workflow_paths.py
Notes:
 - By default runs all gates (check_testing_artifacts, pytest, validate_layers, scan_forbidden_imports)
   per `GATES` and writes `.local/workflow-artifacts/prep.md`.
 - Pass --skip-gates when the agent has already run and verified gates independently; the script
   then only writes the attribution/stamp block and marks gates as externally verified.
 - The script is the canonical source of the prep artifact; agent writes resolved findings,
   HEAD SHA, and residual risks into the file after the script creates the header.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

_PR_DIR = Path(__file__).resolve().parent
if str(_PR_DIR) not in sys.path:
    sys.path.insert(0, str(_PR_DIR))

from local_workflow_paths import PREP_MD, ensure_workflow_artifacts_dir


GATES = [
    ["python", "scripts/pr/check_testing_artifacts.py"],
    ["python", "-m", "pytest", "-q"],
    ["python", "scripts/architecture/validate_layers.py"],
    ["python", "scripts/architecture/scan_forbidden_imports.py"],
]


def _run(cmd: list[str]) -> tuple[int, str]:
    normalized = list(cmd)
    if normalized and normalized[0] == "python" and shutil.which("python") is None:
        normalized[0] = sys.executable
    proc = subprocess.run(normalized, capture_output=True, text=True)
    output = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, output.strip()


def _current_branch() -> str:
    proc = subprocess.run(
        ["git", "branch", "--show-current"], capture_output=True, text=True
    )
    return proc.stdout.strip() or "unknown"


def _head_sha() -> str:
    proc = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True)
    return proc.stdout.strip() or "unknown"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run PR prepare gates and artifact generation.")
    parser.add_argument("--pr", required=True, help="PR number or URL")
    parser.add_argument("--actor", required=True, help="Actor display name performing prepare action")
    parser.add_argument(
        "--agents",
        required=True,
        help='Agent list, e.g. "review-pr | prepare-pr | merge-pr"',
    )
    parser.add_argument(
        "--skip-gates",
        action="store_true",
        default=False,
        help=(
            "Skip running gates inside the script. Use when the agent already ran and "
            "verified all gates; the artifact will record gates as externally verified."
        ),
    )
    args = parser.parse_args()

    ensure_workflow_artifacts_dir()
    prep_file = PREP_MD

    branch = _current_branch()
    head_sha = _head_sha()

    lines = [
        f"# Prepare Artifact ({args.pr})",
        "",
        "## Attribution",
        f"- Action-By: {args.actor}",
        f"- Prepared-By: {args.actor}",
        "- GitHub-User: @SavinRazvan",
        f"- Agent/s: {args.agents}",
        f"- Branch: {branch}",
        f"- HEAD SHA: {head_sha}",
        "",
        "## Gate Results",
    ]

    failed = False
    if args.skip_gates:
        lines.append("- gates: externally verified by agent before this script call")
    else:
        for gate in GATES:
            code, output = _run(gate)
            label = "PASS" if code == 0 else "FAIL"
            lines.append(f"- `{ ' '.join(gate) }` -> {label}")
            if code != 0:
                failed = True
                lines.append("")
                lines.append("```text")
                lines.append(output)
                lines.append("```")

    lines.extend(
        [
            "",
            "## Status",
            "- PR is ready for /merge-pr" if not failed else "- NOT READY",
            "",
            "## Agent Notes",
            "- (agent: add resolved findings, residual risks, and follow-ups below)",
        ]
    )
    prep_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Created {prep_file}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
