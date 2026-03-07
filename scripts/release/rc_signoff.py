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
import json
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


@dataclass(frozen=True)
class GovernanceAlertResult:
    enabled: bool
    advisory_only: bool
    metrics_path: str
    metrics_available: bool
    cost_utilization_threshold: float
    rejection_rate_threshold: float
    cost_utilization_ratio: float | None
    rejection_rate: float | None
    alerts: list[str]
    result: str
    output: str


@dataclass(frozen=True)
class RuntimeSnapshotsResult:
    enabled: bool
    advisory_only: bool
    snapshot_path: str
    available: bool
    before_captured: bool
    after_captured: bool
    before_runs_total: int | None
    after_runs_total: int | None
    output: str


@dataclass(frozen=True)
class UiE2EAutomationResult:
    enabled: bool
    advisory_only: bool
    artifact_path: str
    available: bool
    result: str
    stages_passed_total: int | None
    stages_failed_total: int | None
    output: str


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

DEFAULT_GOVERNANCE_METRICS_PATH = ".local/byoc-governance-metrics.json"
DEFAULT_RUNTIME_SNAPSHOTS_PATH = ".local/ui-smoke-runtime-snapshots.json"
DEFAULT_UI_E2E_AUTOMATION_PATH = ".local/ui-e2e-smoke.json"

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


def _safe_float(raw: object) -> float | None:
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _run_governance_alerts(
    *,
    metrics_path: str,
    cost_utilization_threshold: float,
    rejection_rate_threshold: float,
) -> GovernanceAlertResult:
    path = Path(metrics_path)
    advisory_only = True
    if not path.exists():
        return GovernanceAlertResult(
            enabled=True,
            advisory_only=advisory_only,
            metrics_path=str(path),
            metrics_available=False,
            cost_utilization_threshold=cost_utilization_threshold,
            rejection_rate_threshold=rejection_rate_threshold,
            cost_utilization_ratio=None,
            rejection_rate=None,
            alerts=[],
            result="UNAVAILABLE",
            output="Governance metrics file not found; section is advisory-only.",
        )

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return GovernanceAlertResult(
            enabled=True,
            advisory_only=advisory_only,
            metrics_path=str(path),
            metrics_available=False,
            cost_utilization_threshold=cost_utilization_threshold,
            rejection_rate_threshold=rejection_rate_threshold,
            cost_utilization_ratio=None,
            rejection_rate=None,
            alerts=[],
            result="UNAVAILABLE",
            output=f"Failed to parse governance metrics: {exc}",
        )

    cost_ratio = _safe_float(payload.get("cost", {}).get("utilization_ratio"))
    rejection_rate = _safe_float(payload.get("submissions", {}).get("rejection_rate"))
    alerts: list[str] = []
    if cost_ratio is not None and cost_ratio >= cost_utilization_threshold:
        alerts.append("cost_utilization_threshold_exceeded")
    if rejection_rate is not None and rejection_rate >= rejection_rate_threshold:
        alerts.append("rejection_rate_threshold_exceeded")
    missing_fields: list[str] = []
    if cost_ratio is None:
        missing_fields.append("cost.utilization_ratio")
    if rejection_rate is None:
        missing_fields.append("submissions.rejection_rate")

    if missing_fields:
        output = (
            "Governance metrics parsed with missing fields: "
            + ", ".join(missing_fields)
            + ". Section remains advisory-only."
        )
        return GovernanceAlertResult(
            enabled=True,
            advisory_only=advisory_only,
            metrics_path=str(path),
            metrics_available=False,
            cost_utilization_threshold=cost_utilization_threshold,
            rejection_rate_threshold=rejection_rate_threshold,
            cost_utilization_ratio=cost_ratio,
            rejection_rate=rejection_rate,
            alerts=alerts,
            result="UNAVAILABLE",
            output=output,
        )
    return GovernanceAlertResult(
        enabled=True,
        advisory_only=advisory_only,
        metrics_path=str(path),
        metrics_available=True,
        cost_utilization_threshold=cost_utilization_threshold,
        rejection_rate_threshold=rejection_rate_threshold,
        cost_utilization_ratio=cost_ratio,
        rejection_rate=rejection_rate,
        alerts=alerts,
        result="ALERT" if alerts else "PASS",
        output="Governance metrics evaluated against configured advisory thresholds.",
    )


def _run_runtime_snapshots(snapshot_path: str) -> RuntimeSnapshotsResult:
    path = Path(snapshot_path)
    advisory_only = True
    if not path.exists():
        return RuntimeSnapshotsResult(
            enabled=True,
            advisory_only=advisory_only,
            snapshot_path=str(path),
            available=False,
            before_captured=False,
            after_captured=False,
            before_runs_total=None,
            after_runs_total=None,
            output="Runtime snapshot file not found; section is advisory-only.",
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return RuntimeSnapshotsResult(
            enabled=True,
            advisory_only=advisory_only,
            snapshot_path=str(path),
            available=False,
            before_captured=False,
            after_captured=False,
            before_runs_total=None,
            after_runs_total=None,
            output=f"Failed to parse runtime snapshots file: {exc}",
        )
    before = payload.get("before", {}) if isinstance(payload, dict) else {}
    after = payload.get("after", {}) if isinstance(payload, dict) else {}
    before_runs = before.get("runtime_runs", {}) if isinstance(before, dict) else {}
    after_runs = after.get("runtime_runs", {}) if isinstance(after, dict) else {}
    before_payload = before_runs.get("payload", {}) if isinstance(before_runs, dict) else {}
    after_payload = after_runs.get("payload", {}) if isinstance(after_runs, dict) else {}
    before_total_raw = before_payload.get("total")
    after_total_raw = after_payload.get("total")
    before_total = int(before_total_raw) if isinstance(before_total_raw, int) else None
    after_total = int(after_total_raw) if isinstance(after_total_raw, int) else None
    before_captured = isinstance(before, dict) and bool(before)
    after_captured = isinstance(after, dict) and bool(after)
    return RuntimeSnapshotsResult(
        enabled=True,
        advisory_only=advisory_only,
        snapshot_path=str(path),
        available=True,
        before_captured=before_captured,
        after_captured=after_captured,
        before_runs_total=before_total,
        after_runs_total=after_total,
        output="Runtime snapshots loaded and linked as advisory evidence.",
    )


def _run_ui_e2e_automation(artifact_path: str) -> UiE2EAutomationResult:
    path = Path(artifact_path)
    advisory_only = True
    if not path.exists():
        return UiE2EAutomationResult(
            enabled=True,
            advisory_only=advisory_only,
            artifact_path=str(path),
            available=False,
            result="UNAVAILABLE",
            stages_passed_total=None,
            stages_failed_total=None,
            output="UI E2E automation artifact not found; section is advisory-only.",
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return UiE2EAutomationResult(
            enabled=True,
            advisory_only=advisory_only,
            artifact_path=str(path),
            available=False,
            result="UNAVAILABLE",
            stages_passed_total=None,
            stages_failed_total=None,
            output=f"Failed to parse UI E2E automation artifact: {exc}",
        )

    result = str(payload.get("status", "")).strip().upper()
    if result not in {"PASS", "FAIL"}:
        result = "UNAVAILABLE"
    return UiE2EAutomationResult(
        enabled=True,
        advisory_only=advisory_only,
        artifact_path=str(path),
        available=True,
        result=result,
        stages_passed_total=int(payload.get("stages_passed_total", 0)),
        stages_failed_total=int(payload.get("stages_failed_total", 0)),
        output="UI E2E automation artifact loaded and linked as advisory evidence.",
    )


def _write_report(
    *,
    out_path: Path,
    started_at: datetime,
    ended_at: datetime,
    context: ExecutionContext,
    gate_results: list[GateResult],
    data_safety: DataSafetyResult,
    governance_alerts: GovernanceAlertResult,
    runtime_snapshots: RuntimeSnapshotsResult,
    ui_e2e_automation: UiE2EAutomationResult,
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
    lines.append("## Governance Alerts")
    lines.append(f"- Enabled: `{'true' if governance_alerts.enabled else 'false'}`")
    lines.append(f"- Advisory Only: `{'true' if governance_alerts.advisory_only else 'false'}`")
    lines.append(f"- Metrics Path: `{governance_alerts.metrics_path}`")
    lines.append(f"- Metrics Available: `{'true' if governance_alerts.metrics_available else 'false'}`")
    lines.append(f"- Cost Utilization Threshold: `{governance_alerts.cost_utilization_threshold:.4f}`")
    lines.append(f"- Rejection Rate Threshold: `{governance_alerts.rejection_rate_threshold:.4f}`")
    lines.append(
        "- Cost Utilization Ratio: "
        + (
            f"`{governance_alerts.cost_utilization_ratio:.4f}`"
            if governance_alerts.cost_utilization_ratio is not None
            else "`n/a`"
        )
    )
    lines.append(
        "- Rejection Rate: "
        + (
            f"`{governance_alerts.rejection_rate:.4f}`"
            if governance_alerts.rejection_rate is not None
            else "`n/a`"
        )
    )
    lines.append(f"- Alert Count: `{len(governance_alerts.alerts)}`")
    lines.append(f"- Alerts: `{', '.join(governance_alerts.alerts) if governance_alerts.alerts else 'none'}`")
    lines.append(f"- Result: `{governance_alerts.result}`")
    lines.append("```text")
    lines.append(governance_alerts.output or "(no output)")
    lines.append("```")
    lines.append("")
    lines.append("## Runtime Snapshots")
    lines.append(f"- Enabled: `{'true' if runtime_snapshots.enabled else 'false'}`")
    lines.append(f"- Advisory Only: `{'true' if runtime_snapshots.advisory_only else 'false'}`")
    lines.append(f"- Snapshot Path: `{runtime_snapshots.snapshot_path}`")
    lines.append(f"- Available: `{'true' if runtime_snapshots.available else 'false'}`")
    lines.append(f"- Before Captured: `{'true' if runtime_snapshots.before_captured else 'false'}`")
    lines.append(f"- After Captured: `{'true' if runtime_snapshots.after_captured else 'false'}`")
    lines.append(
        "- Before Runs Total: "
        + (
            f"`{runtime_snapshots.before_runs_total}`"
            if runtime_snapshots.before_runs_total is not None
            else "`n/a`"
        )
    )
    lines.append(
        "- After Runs Total: "
        + (
            f"`{runtime_snapshots.after_runs_total}`"
            if runtime_snapshots.after_runs_total is not None
            else "`n/a`"
        )
    )
    lines.append("```text")
    lines.append(runtime_snapshots.output or "(no output)")
    lines.append("```")
    lines.append("")
    lines.append("## UI E2E Automation")
    lines.append(f"- Enabled: `{'true' if ui_e2e_automation.enabled else 'false'}`")
    lines.append(f"- Advisory Only: `{'true' if ui_e2e_automation.advisory_only else 'false'}`")
    lines.append(f"- Artifact Path: `{ui_e2e_automation.artifact_path}`")
    lines.append(f"- Available: `{'true' if ui_e2e_automation.available else 'false'}`")
    lines.append(f"- Result: `{ui_e2e_automation.result}`")
    lines.append(
        "- Stages Passed Total: "
        + (
            f"`{ui_e2e_automation.stages_passed_total}`"
            if ui_e2e_automation.stages_passed_total is not None
            else "`n/a`"
        )
    )
    lines.append(
        "- Stages Failed Total: "
        + (
            f"`{ui_e2e_automation.stages_failed_total}`"
            if ui_e2e_automation.stages_failed_total is not None
            else "`n/a`"
        )
    )
    lines.append("```text")
    lines.append(ui_e2e_automation.output or "(no output)")
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
    parser.add_argument(
        "--governance-metrics-in",
        default=DEFAULT_GOVERNANCE_METRICS_PATH,
        help="Path to governance metrics JSON input used for advisory alert evaluation.",
    )
    parser.add_argument(
        "--runtime-snapshots-in",
        default=DEFAULT_RUNTIME_SNAPSHOTS_PATH,
        help="Path to local runtime snapshot JSON used for advisory evidence linkage.",
    )
    parser.add_argument(
        "--ui-e2e-automation-in",
        default=DEFAULT_UI_E2E_AUTOMATION_PATH,
        help="Path to local UI E2E automation artifact JSON used for advisory evidence linkage.",
    )
    args = parser.parse_args()

    started_at = datetime.now(UTC)
    context = _execution_context()
    missing_links = _ensure_required_links()
    data_safety_required = bool(args.require_data_safety) or _env_bool(
        "EXO_RC_SIGNOFF_REQUIRE_DATA_SAFETY", default=False
    )
    governance_cost_threshold = float(os.getenv("EXO_GOV_ALERT_COST_UTIL_THRESHOLD", "0.90"))
    governance_rejection_threshold = float(os.getenv("EXO_GOV_ALERT_REJECTION_RATE_THRESHOLD", "0.10"))
    gate_results: list[GateResult] = []

    if not missing_links:
        for gate in GATES:
            result = _run_gate(gate)
            gate_results.append(result)
            if not result.ok:
                break
    data_safety_result = _run_data_safety(required=data_safety_required)
    governance_alerts_result = _run_governance_alerts(
        metrics_path=str(args.governance_metrics_in),
        cost_utilization_threshold=governance_cost_threshold,
        rejection_rate_threshold=governance_rejection_threshold,
    )
    runtime_snapshots_result = _run_runtime_snapshots(str(args.runtime_snapshots_in))
    ui_e2e_automation_result = _run_ui_e2e_automation(str(args.ui_e2e_automation_in))

    ended_at = datetime.now(UTC)
    out_path = Path(args.out)
    _write_report(
        out_path=out_path,
        started_at=started_at,
        ended_at=ended_at,
        context=context,
        gate_results=gate_results,
        data_safety=data_safety_result,
        governance_alerts=governance_alerts_result,
        runtime_snapshots=runtime_snapshots_result,
        ui_e2e_automation=ui_e2e_automation_result,
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
