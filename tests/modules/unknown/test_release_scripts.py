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
                "```text",
                "ok",
                "```",
                "",
                "### validate_layers: FAIL",
                "```text",
                "failed",
                "```",
                "",
                "## Overall",
                "- Result: `FAIL`",
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
    assert payload["overall"]["missing_evidence_links"] == [
        "docs/operations/byoc-artifact-integrity-dashboard.md"
    ]
    assert payload["overall"]["failed_gates"] == ["validate_layers"]
