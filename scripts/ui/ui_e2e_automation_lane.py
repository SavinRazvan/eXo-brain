"""
File: ui_e2e_automation_lane.py
Path: scripts/ui/ui_e2e_automation_lane.py
Role: Run repeatable local UI E2E automation lane and emit advisory evidence artifacts.
Used By:
 - Makefile
 - .github/workflows/ui-e2e-nonblocking.yml
Depends On:
 - scripts/ui/local_ui_readiness_smoke.py
Notes:
 - Wraps the existing local smoke flow and normalizes output for RC evidence ingestion.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _parse_stage_lines(output: str) -> list[dict[str, str]]:
    stages: list[dict[str, str]] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if line.startswith("[PASS] ") or line.startswith("[FAIL] "):
            marker = "pass" if line.startswith("[PASS] ") else "fail"
            name = line[7:].strip()
            stages.append({"name": name, "status": marker})
    return stages


def _build_command(args: argparse.Namespace) -> list[str]:
    cmd = [
        sys.executable,
        "scripts/ui/local_ui_readiness_smoke.py",
        "--host",
        str(args.host),
        "--port",
        str(args.port),
        "--tenant-id",
        str(args.tenant_id),
        "--startup-timeout-seconds",
        str(args.startup_timeout_seconds),
        "--request-timeout-seconds",
        str(args.request_timeout_seconds),
    ]
    if bool(args.skip_ui_build):
        cmd.append("--skip-ui-build")
    return cmd


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run local UI E2E automation lane and write normalized evidence artifacts."
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--tenant-id", default="t1")
    parser.add_argument("--startup-timeout-seconds", type=float, default=30.0)
    parser.add_argument("--request-timeout-seconds", type=float, default=20.0)
    parser.add_argument("--skip-ui-build", action="store_true")
    parser.add_argument(
        "--out",
        default=".local/ui-e2e-smoke.json",
        help="Path for normalized UI E2E lane summary JSON.",
    )
    parser.add_argument(
        "--log-out",
        default=".local/ui-e2e-smoke.log",
        help="Path for lane execution log output.",
    )
    args = parser.parse_args()

    root = _repo_root()
    out_path = Path(args.out)
    log_path = Path(args.log_out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    command = _build_command(args)
    started = time.time()
    completed = subprocess.run(
        command,
        cwd=str(root),
        check=False,
        capture_output=True,
        text=True,
    )
    ended = time.time()
    combined_output = ((completed.stdout or "") + "\n" + (completed.stderr or "")).strip()
    stages = _parse_stage_lines(combined_output)
    passed_count = sum(1 for stage in stages if stage["status"] == "pass")
    failed_count = sum(1 for stage in stages if stage["status"] == "fail")
    snapshots_path = root / ".local" / "ui-smoke-runtime-snapshots.json"
    summary = {
        "schema_version": "1.0",
        "lane": "ui_e2e_automation",
        "status": "pass" if completed.returncode == 0 else "fail",
        "exit_code": int(completed.returncode),
        "started_at_epoch": int(started),
        "ended_at_epoch": int(ended),
        "duration_ms": int((ended - started) * 1000),
        "command": command,
        "tenant_id": str(args.tenant_id),
        "host": str(args.host),
        "port": int(args.port),
        "stages": stages,
        "stages_passed_total": passed_count,
        "stages_failed_total": failed_count,
        "runtime_snapshots_path": str(snapshots_path),
        "runtime_snapshots_available": snapshots_path.exists(),
        "advisory_only": True,
    }
    out_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    log_path.write_text(combined_output + ("\n" if combined_output else ""), encoding="utf-8")

    print(f"UI E2E lane summary written to {out_path}")
    print(f"UI E2E lane log written to {log_path}")
    if completed.returncode != 0:
        print("UI E2E lane failed.")
        return int(completed.returncode or 1)
    print("UI E2E lane passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

