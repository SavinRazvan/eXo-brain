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
import os
import subprocess
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True)
class GateCommand:
    name: str
    command: list[str]


@dataclass(frozen=True)
class ExecutionContext:
    actor: str
    repo: str
    event_name: str
    ref_name: str
    commit_sha: str
    pull_request_number: str
    run_id: str
    run_url: str


@dataclass(frozen=True)
class GateResult:
    gate: GateCommand
    ok: bool
    exit_code: int
    duration_ms: int
    output: str


@dataclass(frozen=True)
class DataSafetyResult:
    enabled: bool
    required: bool
    command: list[str]
    ok: bool
    exit_code: int
    duration_ms: int
    output: str
    meta_path: str


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

DATA_SAFETY_COMMAND: tuple[str, ...] = (
    "python",
    "scripts/release/local_data_safety.py",
    "validate",
    "--meta-out",
    ".local/db-validate-meta.json",
)

REQUIRED_EVIDENCE_LINKS: tuple[str, ...] = (
    "docs/plans/tenant-tool-execution-architecture.md",
    "docs/operations/byoc-artifact-integrity-dashboard.md",
    ".cursor/research-for-refactor/18-enterprise-operational-runbooks.md",
    ".cursor/research-for-refactor/26-deployment-profiles-matrix.md",
    ".cursor/research-for-refactor/12-bootstrap-checklist.md",
    ".cursor/research-for-refactor/06-mvp-build-sequence.md",
)


def _run_gate(gate: GateCommand) -> GateResult:
    started = time.perf_counter()
    completed = subprocess.run(
        gate.command,
        capture_output=True,
        text=True,
        check=False,
    )
    duration_ms = int((time.perf_counter() - started) * 1000)
    output = (completed.stdout + "\n" + completed.stderr).strip()
    return GateResult(
        gate=gate,
        ok=completed.returncode == 0,
        exit_code=completed.returncode,
        duration_ms=duration_ms,
        output=output,
    )


def _command_output(command: list[str]) -> str:
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        return ""
    return completed.stdout.strip()


def _git_commit_sha() -> str:
    return _command_output(["git", "rev-parse", "HEAD"]) or "unknown"


def _git_ref_name() -> str:
    return _command_output(["git", "rev-parse", "--abbrev-ref", "HEAD"]) or "unknown"


def _execution_context() -> ExecutionContext:
    actor = os.getenv("GITHUB_ACTOR", "local")
    repo = os.getenv("GITHUB_REPOSITORY", _command_output(["git", "remote", "get-url", "origin"]) or "unknown")
    event_name = os.getenv("GITHUB_EVENT_NAME", "local")
    ref_name = os.getenv("GITHUB_REF_NAME", _git_ref_name())
    commit_sha = os.getenv("GITHUB_SHA", _git_commit_sha())
    pull_request_number = os.getenv("PR_NUMBER", os.getenv("GITHUB_PR_NUMBER", "n/a"))
    run_id = os.getenv("GITHUB_RUN_ID", "local")
    server_url = os.getenv("GITHUB_SERVER_URL", "https://github.com")
    run_url = "n/a"
    if run_id != "local" and repo != "unknown":
        run_url = f"{server_url}/{repo}/actions/runs/{run_id}"
    return ExecutionContext(
        actor=actor,
        repo=repo,
        event_name=event_name,
        ref_name=ref_name,
        commit_sha=commit_sha,
        pull_request_number=pull_request_number,
        run_id=run_id,
        run_url=run_url,
    )


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _ensure_required_links() -> list[str]:
    missing: list[str] = []
    for rel_path in REQUIRED_EVIDENCE_LINKS:
        if not Path(rel_path).exists():
            missing.append(rel_path)
    return missing


def _run_data_safety(required: bool) -> DataSafetyResult:
    command = list(DATA_SAFETY_COMMAND)
    started = time.perf_counter()
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    duration_ms = int((time.perf_counter() - started) * 1000)
    output = (completed.stdout + "\n" + completed.stderr).strip()
    return DataSafetyResult(
        enabled=True,
        required=required,
        command=command,
        ok=completed.returncode == 0,
        exit_code=int(completed.returncode),
        duration_ms=duration_ms,
        output=output,
        meta_path=".local/db-validate-meta.json",
    )


def _write_report(
    *,
    out_path: Path,
    started_at: datetime,
    ended_at: datetime,
    context: ExecutionContext,
    gate_results: list[GateResult],
    data_safety: DataSafetyResult,
    missing_links: list[str],
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append("# Release Candidate Signoff Evidence")
    lines.append("")
    lines.append(f"- Started: `{started_at.isoformat()}`")
    lines.append(f"- Ended: `{ended_at.isoformat()}`")
    lines.append("")
    lines.append("## Execution Context")
    lines.append(f"- Actor: `{context.actor}`")
    lines.append(f"- Repository: `{context.repo}`")
    lines.append(f"- Event: `{context.event_name}`")
    lines.append(f"- Ref: `{context.ref_name}`")
    lines.append(f"- Commit: `{context.commit_sha}`")
    lines.append(f"- PR Number: `{context.pull_request_number}`")
    lines.append(f"- Run ID: `{context.run_id}`")
    lines.append(f"- Run URL: `{context.run_url}`")
    lines.append("")
    lines.append("## Required Evidence Links")
    for rel_path in REQUIRED_EVIDENCE_LINKS:
        marker = "OK" if rel_path not in missing_links else "MISSING"
        lines.append(f"- [{marker}] `{rel_path}`")
    lines.append("")
    lines.append("## Gate Results")
    for result in gate_results:
        status = "PASS" if result.ok else "FAIL"
        command_str = " ".join(result.gate.command)
        lines.append(f"### {result.gate.name}: {status}")
        lines.append(f"- Command: `{command_str}`")
        lines.append(f"- Exit Code: `{result.exit_code}`")
        lines.append(f"- Duration Ms: `{result.duration_ms}`")
        lines.append("```text")
        lines.append(result.output or "(no output)")
        lines.append("```")
        lines.append("")
    lines.append("## Local Data Safety")
    lines.append(f"- Enabled: `{'true' if data_safety.enabled else 'false'}`")
    lines.append(f"- Required: `{'true' if data_safety.required else 'false'}`")
    lines.append(f"- Mode: `{'required' if data_safety.required else 'advisory'}`")
    lines.append(f"- Command: `{' '.join(data_safety.command)}`")
    lines.append(f"- Exit Code: `{data_safety.exit_code}`")
    lines.append(f"- Duration Ms: `{data_safety.duration_ms}`")
    lines.append(f"- Result: `{'PASS' if data_safety.ok else 'FAIL'}`")
    lines.append(f"- Meta Path: `{data_safety.meta_path}`")
    lines.append("```text")
    lines.append(data_safety.output or "(no output)")
    lines.append("```")
    lines.append("")
    overall_pass = not missing_links and all(result.ok for result in gate_results)
    if data_safety.required and not data_safety.ok:
        overall_pass = False
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
    parser.add_argument(
        "--require-data-safety",
        action="store_true",
        help="Fail signoff when local data safety validation fails.",
    )
    args = parser.parse_args()

    started_at = datetime.now(UTC)
    context = _execution_context()
    missing_links = _ensure_required_links()
    data_safety_required = bool(args.require_data_safety) or _env_bool(
        "EXO_RC_SIGNOFF_REQUIRE_DATA_SAFETY", default=False
    )
    gate_results: list[GateResult] = []

    if not missing_links:
        for gate in GATES:
            result = _run_gate(gate)
            gate_results.append(result)
            if not result.ok:
                break
    data_safety_result = _run_data_safety(required=data_safety_required)

    ended_at = datetime.now(UTC)
    out_path = Path(args.out)
    _write_report(
        out_path=out_path,
        started_at=started_at,
        ended_at=ended_at,
        context=context,
        gate_results=gate_results,
        data_safety=data_safety_result,
        missing_links=missing_links,
    )

    if missing_links:
        print("RC signoff failed: missing required evidence links.")
        for item in missing_links:
            print(f" - {item}")
        print(f"Evidence written to {out_path}")
        return 1

    failed_gate = next((result.gate.name for result in gate_results if not result.ok), "")
    if failed_gate:
        print(f"RC signoff failed: gate '{failed_gate}' did not pass.")
        print(f"Evidence written to {out_path}")
        return 1
    if data_safety_required and not data_safety_result.ok:
        print("RC signoff failed: required local data safety validation did not pass.")
        print(f"Evidence written to {out_path}")
        return 1

    print("RC signoff passed.")
    print(f"Evidence written to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
