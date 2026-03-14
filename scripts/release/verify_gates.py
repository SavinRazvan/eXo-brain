"""
File: verify_gates.py
Path: scripts/release/verify_gates.py
Role: Runs required release gates and writes a machine-readable evidence report.
Used By:
 - .github/workflows/release-candidate.yml
Depends On:
 - subprocess
 - json
 - pathlib
Notes:
 - Fails fast when any mandatory gate fails.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


REQUIRED_GATES: list[list[str]] = [
    ["python", "-m", "pytest", "-q"],
    ["python", "scripts/architecture/validate_layers.py"],
    ["python", "scripts/architecture/scan_forbidden_imports.py"],
    [
        "python",
        "scripts/perf/option_c_load_profiles.py",
        "--enforce",
        "--thresholds-json",
        "configs/release/option_c_slo_thresholds.json",
        "--json-out",
        "artifacts/evidence/option_c_load_profiles.json",
    ],
    [
        "python",
        "scripts/perf/ingress_budget_report.py",
        "--enforce",
        "--thresholds-json",
        "configs/release/ingress_budget_thresholds.json",
        "--json-out",
        "artifacts/evidence/ingress_budget_report.json",
    ],
]


def _run(cmd: list[str]) -> tuple[int, str]:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    output = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, output.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run release candidate gate checks.")
    parser.add_argument("--out", default="artifacts/evidence/release_gates.json", help="Evidence output path")
    args = parser.parse_args()

    results: list[dict[str, object]] = []
    failed = False
    for gate in REQUIRED_GATES:
        command = " ".join(gate)
        print(f"[gate] running: {command}")
        code, output = _run(gate)
        status = "pass" if code == 0 else "fail"
        results.append(
            {
                "command": command,
                "exit_code": code,
                "status": status,
                "output": output,
            }
        )
        if code != 0:
            failed = True
            print(f"[gate] FAILED: {command} (exit={code})", file=sys.stderr)
            if output:
                print(output, file=sys.stderr)
        else:
            print(f"[gate] passed: {command}")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "summary": {
            "failed": failed,
            "total_gates": len(results),
            "passed_gates": len([r for r in results if r["status"] == "pass"]),
        },
        "results": results,
    }
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote gate evidence to {out_path}")
    if failed:
        print("One or more release gates failed. See logs above and evidence JSON.", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
