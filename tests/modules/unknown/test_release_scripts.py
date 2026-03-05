"""
File: test_release_scripts.py
Path: tests/modules/unknown/test_release_scripts.py
Role: Validates release governance scripts used by CI/CD workflows.
Used By:
 - .github/workflows/release-candidate.yml
 - .github/workflows/progressive-deploy.yml
Depends On:
 - scripts/release/verify_gates.py
 - scripts/release/verify_provenance.py
 - scripts/release/rollback_release.py
Notes:
 - Keeps release workflow helpers deterministic and testable.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / "scripts" / "release"


def _load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_verify_gates_writes_evidence(tmp_path: Path, monkeypatch) -> None:
    module = _load_module("verify_gates_script", SCRIPTS_DIR / "verify_gates.py")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(module, "REQUIRED_GATES", [["python", "-c", "print('ok')"]])
    monkeypatch.setattr(sys, "argv", ["verify_gates.py", "--out", "artifacts/evidence/gates.json"])
    assert module.main() == 0

    payload = json.loads((tmp_path / "artifacts" / "evidence" / "gates.json").read_text(encoding="utf-8"))
    assert payload["summary"]["failed"] is False
    assert payload["summary"]["passed_gates"] == 1


def test_verify_provenance_writes_metadata(tmp_path: Path, monkeypatch) -> None:
    module = _load_module("verify_provenance_script", SCRIPTS_DIR / "verify_provenance.py")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GITHUB_SHA", "abc123")
    monkeypatch.setenv("GITHUB_REF", "refs/heads/main")
    monkeypatch.setenv("GITHUB_REPOSITORY", "SavinRazvan/eXo-brain")
    monkeypatch.setattr(sys, "argv", ["verify_provenance.py", "--out", "artifacts/evidence/provenance.json"])
    assert module.main() == 0

    payload = json.loads((tmp_path / "artifacts" / "evidence" / "provenance.json").read_text(encoding="utf-8"))
    assert payload["source"]["sha"] == "abc123"
    assert payload["source"]["repository"] == "SavinRazvan/eXo-brain"


def test_rollback_release_writes_evidence(tmp_path: Path, monkeypatch) -> None:
    module = _load_module("rollback_release_script", SCRIPTS_DIR / "rollback_release.py")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "rollback_release.py",
            "--release-ref",
            "a8614a5",
            "--environment",
            "stage",
            "--out",
            "artifacts/evidence/rollback.txt",
        ],
    )
    assert module.main() == 0
    content = (tmp_path / "artifacts" / "evidence" / "rollback.txt").read_text(encoding="utf-8")
    assert "rollback-status: executed" in content
    assert "environment: stage" in content


def test_parse_rc_signoff_writes_normalized_json(tmp_path: Path, monkeypatch) -> None:
    module = _load_module("parse_rc_signoff_script", SCRIPTS_DIR / "parse_rc_signoff.py")
    source = tmp_path / ".local" / "rc-signoff.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(
        "\n".join(
            [
                "# Release Candidate Signoff Evidence",
                "",
                "- Started: `2026-01-01T00:00:00+00:00`",
                "- Ended: `2026-01-01T00:05:00+00:00`",
                "",
                "## Execution Context",
                "- Actor: `bot`",
                "- Repository: `SavinRazvan/eXo-brain`",
                "- Event: `pull_request`",
                "- Ref: `feature/x`",
                "- Commit: `abc123`",
                "- PR Number: `99`",
                "- Run ID: `12345`",
                "- Run URL: `https://github.com/SavinRazvan/eXo-brain/actions/runs/12345`",
                "",
                "## Required Evidence Links",
                "- [OK] `docs/plans/tenant-tool-execution-architecture.md`",
                "- [MISSING] `docs/operations/byoc-artifact-integrity-dashboard.md`",
                "",
                "## Gate Results",
                "### pytest: PASS",
                "- Command: `python -m pytest -q`",
                "- Exit Code: `0`",
                "- Duration Ms: `1200`",
                "```text",
                "ok",
                "```",
                "",
                "### validate_layers: FAIL",
                "- Command: `python scripts/architecture/validate_layers.py`",
                "- Exit Code: `1`",
                "- Duration Ms: `210`",
                "```text",
                "failed",
                "```",
                "",
                "## Local Data Safety",
                "- Enabled: `true`",
                "- Required: `false`",
                "- Mode: `advisory`",
                "- Command: `python scripts/release/local_data_safety.py validate --meta-out .local/db-validate-meta.json`",
                "- Exit Code: `0`",
                "- Duration Ms: `120`",
                "- Result: `PASS`",
                "- Meta Path: `.local/db-validate-meta.json`",
                "```text",
                "DB validation passed",
                "```",
                "",
                "## Overall",
                "- Result: `FAIL`",
                "",
                "## Governance Alerts",
                "- Enabled: `true`",
                "- Advisory Only: `true`",
                "- Metrics Path: `.local/byoc-governance-metrics.json`",
                "- Metrics Available: `true`",
                "- Cost Utilization Threshold: `0.9000`",
                "- Rejection Rate Threshold: `0.1000`",
                "- Cost Utilization Ratio: `0.9100`",
                "- Rejection Rate: `0.0400`",
                "- Alert Count: `1`",
                "- Alerts: `cost_utilization_threshold_exceeded`",
                "- Result: `ALERT`",
                "```text",
                "Governance metrics evaluated against configured advisory thresholds.",
                "```",
                "",
                "## Runtime Snapshots",
                "- Enabled: `true`",
                "- Advisory Only: `true`",
                "- Snapshot Path: `.local/ui-smoke-runtime-snapshots.json`",
                "- Available: `true`",
                "- Before Captured: `true`",
                "- After Captured: `true`",
                "- Before Runs Total: `0`",
                "- After Runs Total: `1`",
                "```text",
                "Runtime snapshots loaded and linked as advisory evidence.",
                "```",
                "",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "parse_rc_signoff.py",
            "--in",
            ".local/rc-signoff.md",
            "--out",
            ".local/rc-signoff.json",
        ],
    )
    assert module.main() == 0

    payload = json.loads((tmp_path / ".local" / "rc-signoff.json").read_text(encoding="utf-8"))
    assert payload["schema_version"] == "1.0"
    assert payload["started_at"] == "2026-01-01T00:00:00+00:00"
    assert payload["context"]["actor"] == "bot"
    assert payload["overall"]["passed"] is False
    assert payload["gates"][0]["command"] == "python -m pytest -q"
    assert payload["gates"][0]["exit_code"] == 0
    assert payload["gates"][0]["duration_ms"] == 1200
    assert payload["data_safety"]["enabled"] is True
    assert payload["data_safety"]["required"] is False
    assert payload["data_safety"]["mode"] == "advisory"
    assert payload["data_safety"]["ok"] is True
    assert payload["data_safety"]["meta_path"] == ".local/db-validate-meta.json"
    assert payload["governance_alerts"]["enabled"] is True
    assert payload["governance_alerts"]["advisory_only"] is True
    assert payload["governance_alerts"]["metrics_available"] is True
    assert payload["governance_alerts"]["alert_count"] == 1
    assert payload["governance_alerts"]["alerts"] == ["cost_utilization_threshold_exceeded"]
    assert payload["governance_alerts"]["result"] == "ALERT"
    assert payload["runtime_snapshots"]["enabled"] is True
    assert payload["runtime_snapshots"]["available"] is True
    assert payload["runtime_snapshots"]["before_runs_total"] == 0
    assert payload["runtime_snapshots"]["after_runs_total"] == 1
    assert payload["overall"]["missing_evidence_links"] == [
        "docs/operations/byoc-artifact-integrity-dashboard.md"
    ]
    assert payload["overall"]["failed_gates"] == ["validate_layers"]


def test_parse_rc_signoff_backward_compatible_without_gate_metadata(tmp_path: Path, monkeypatch) -> None:
    module = _load_module("parse_rc_signoff_script_legacy", SCRIPTS_DIR / "parse_rc_signoff.py")
    source = tmp_path / ".local" / "rc-signoff.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(
        "\n".join(
            [
                "# Release Candidate Signoff Evidence",
                "",
                "- Started: `2026-01-01T00:00:00+00:00`",
                "- Ended: `2026-01-01T00:05:00+00:00`",
                "",
                "## Gate Results",
                "### pytest: PASS",
                "```text",
                "ok",
                "```",
                "",
                "## Overall",
                "- Result: `PASS`",
                "",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "parse_rc_signoff.py",
            "--in",
            ".local/rc-signoff.md",
            "--out",
            ".local/rc-signoff.json",
        ],
    )
    assert module.main() == 0
    payload = json.loads((tmp_path / ".local" / "rc-signoff.json").read_text(encoding="utf-8"))
    assert payload["overall"]["passed"] is True
    assert payload["gates"][0]["command"] == ""
    assert payload["gates"][0]["exit_code"] is None
    assert payload["gates"][0]["duration_ms"] is None
    assert payload["data_safety"]["enabled"] is False
    assert payload["data_safety"]["ok"] is None
    assert payload["governance_alerts"]["enabled"] is False
    assert payload["governance_alerts"]["alerts"] == []
    assert payload["runtime_snapshots"]["enabled"] is False
    assert payload["runtime_snapshots"]["available"] is False


def test_rc_signoff_writes_data_safety_section(tmp_path: Path, monkeypatch) -> None:
    module = _load_module("rc_signoff_script", SCRIPTS_DIR / "rc_signoff.py")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(module, "REQUIRED_EVIDENCE_LINKS", ())
    monkeypatch.setattr(module, "GATES", (module.GateCommand(name="pytest", command=["python", "-c", "print('ok')"]),))
    monkeypatch.setattr(
        module,
        "_run_data_safety",
        lambda required: module.DataSafetyResult(
            enabled=True,
            required=required,
            command=["python", "scripts/release/local_data_safety.py", "validate"],
            ok=True,
            exit_code=0,
            duration_ms=7,
            output="ok",
            meta_path=".local/db-validate-meta.json",
        ),
    )
    monkeypatch.setattr(
        module,
        "_run_governance_alerts",
        lambda metrics_path, cost_utilization_threshold, rejection_rate_threshold: module.GovernanceAlertResult(
            enabled=True,
            advisory_only=True,
            metrics_path=metrics_path,
            metrics_available=True,
            cost_utilization_threshold=cost_utilization_threshold,
            rejection_rate_threshold=rejection_rate_threshold,
            cost_utilization_ratio=0.91,
            rejection_rate=0.02,
            alerts=["cost_utilization_threshold_exceeded"],
            result="ALERT",
            output="advisory alert",
        ),
    )
    monkeypatch.setattr(
        module,
        "_run_runtime_snapshots",
        lambda snapshot_path: module.RuntimeSnapshotsResult(
            enabled=True,
            advisory_only=True,
            snapshot_path=snapshot_path,
            available=True,
            before_captured=True,
            after_captured=True,
            before_runs_total=0,
            after_runs_total=1,
            output="runtime snapshots linked",
        ),
    )
    monkeypatch.setattr(sys, "argv", ["rc_signoff.py", "--out", ".local/rc-signoff.md"])
    assert module.main() == 0
    content = (tmp_path / ".local" / "rc-signoff.md").read_text(encoding="utf-8")
    assert "## Local Data Safety" in content
    assert "## Governance Alerts" in content
    assert "## Runtime Snapshots" in content
    assert "- Alert Count: `1`" in content
    assert "- Result: `PASS`" in content
