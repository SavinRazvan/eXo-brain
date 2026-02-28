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
Notes:
 - Captures verification summary into .local/prep.md.
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


GATES = [
    ["python", "-m", "pytest", "-q"],
    ["python", "scripts/architecture/validate_layers.py"],
    ["python", "scripts/architecture/scan_forbidden_imports.py"],
]


def _run(cmd: list[str]) -> tuple[int, str]:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    output = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, output.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run PR prepare gates and artifact generation.")
    parser.add_argument("--pr", required=True, help="PR number or URL")
    args = parser.parse_args()

    local_dir = Path(".local")
    local_dir.mkdir(exist_ok=True)
    prep_file = local_dir / "prep.md"

    lines = [f"# Prepare Artifact ({args.pr})", "", "## Gate Results"]
    failed = False
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

    lines.extend(["", "## Status", "- PR is ready for /merge-pr" if not failed else "- NOT READY"])
    prep_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Created {prep_file}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
