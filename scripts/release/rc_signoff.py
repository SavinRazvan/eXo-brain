"""
File: rc_signoff.py
Path: scripts/release/rc_signoff.py
Role: Runs release-candidate signoff gates and writes a single evidence artifact.
Used By:
 - Makefile
 - release managers
Depends On:
 - subprocess
 - pathlib
 - datetime
Notes:
 - Fails fast on missing required evidence-link files.
"""

from __future__ import annotations

import argparse
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True)
class GateCommand:
    name: str
    command: list[str]


GATES: tuple[GateCommand, ...] = (
    GateCommand(name="pytest", command=["python", "-m", "pytest", "-q"]),
    GateCommand(
        name="validate_layers",
        command=["python", "scripts/architecture/validate_layers.py"],
    ),
    GateCommand(
        name="scan_forbidden_imports",
        command=["python", "scripts/architecture/scan_forbidden_imports.py"],
    ),
)

REQUIRED_EVIDENCE_LINKS: tuple[str, ...] = (
    "docs/plans/tenant-tool-execution-architecture.md",
    "docs/operations/byoc-artifact-integrity-dashboard.md",
    ".cursor/research-for-refactor/18-enterprise-operational-runbooks.md",
    ".cursor/research-for-refactor/26-deployment-profiles-matrix.md",
    ".cursor/research-for-refactor/12-bootstrap-checklist.md",
    ".cursor/research-for-refactor/06-mvp-build-sequence.md",
)


def _run_gate(gate: GateCommand) -> tuple[bool, str]:
    completed = subprocess.run(
        gate.command,
        capture_output=True,
        text=True,
        check=False,
    )
    output = (completed.stdout + "\n" + completed.stderr).strip()
    return completed.returncode == 0, output


def _ensure_required_links() -> list[str]:
    missing: list[str] = []
    for rel_path in REQUIRED_EVIDENCE_LINKS:
        if not Path(rel_path).exists():
            missing.append(rel_path)
    return missing


def _write_report(
    *,
    out_path: Path,
    started_at: datetime,
    ended_at: datetime,
    gate_results: list[tuple[GateCommand, bool, str]],
    missing_links: list[str],
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append("# Release Candidate Signoff Evidence")
    lines.append("")
    lines.append(f"- Started: `{started_at.isoformat()}`")
    lines.append(f"- Ended: `{ended_at.isoformat()}`")
    lines.append("")
    lines.append("## Required Evidence Links")
    for rel_path in REQUIRED_EVIDENCE_LINKS:
        marker = "OK" if rel_path not in missing_links else "MISSING"
        lines.append(f"- [{marker}] `{rel_path}`")
    lines.append("")
    lines.append("## Gate Results")
    for gate, ok, output in gate_results:
        status = "PASS" if ok else "FAIL"
        lines.append(f"### {gate.name}: {status}")
        lines.append("```text")
        lines.append(output or "(no output)")
        lines.append("```")
        lines.append("")
    overall_pass = not missing_links and all(ok for _, ok, _ in gate_results)
    lines.append("## Overall")
    lines.append(f"- Result: `{'PASS' if overall_pass else 'FAIL'}`")
    lines.append("")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one-command RC signoff gates.")
    parser.add_argument(
        "--out",
        default=".local/rc-signoff.md",
        help="Path to the generated signoff evidence markdown file.",
    )
    args = parser.parse_args()

    started_at = datetime.now(UTC)
    missing_links = _ensure_required_links()
    gate_results: list[tuple[GateCommand, bool, str]] = []

    if not missing_links:
        for gate in GATES:
            ok, output = _run_gate(gate)
            gate_results.append((gate, ok, output))
            if not ok:
                break

    ended_at = datetime.now(UTC)
    out_path = Path(args.out)
    _write_report(
        out_path=out_path,
        started_at=started_at,
        ended_at=ended_at,
        gate_results=gate_results,
        missing_links=missing_links,
    )

    if missing_links:
        print("RC signoff failed: missing required evidence links.")
        for item in missing_links:
            print(f" - {item}")
        print(f"Evidence written to {out_path}")
        return 1

    failed_gate = next((gate.name for gate, ok, _ in gate_results if not ok), "")
    if failed_gate:
        print(f"RC signoff failed: gate '{failed_gate}' did not pass.")
        print(f"Evidence written to {out_path}")
        return 1

    print("RC signoff passed.")
    print(f"Evidence written to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
