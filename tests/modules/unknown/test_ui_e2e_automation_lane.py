"""
File: test_ui_e2e_automation_lane.py
Path: tests/modules/unknown/test_ui_e2e_automation_lane.py
Role: Validates normalized artifact generation for UI E2E automation lane wrapper script.
Used By:
 - pytest
Depends On:
 - scripts/ui/ui_e2e_automation_lane.py
Notes:
 - Uses monkeypatch to keep execution deterministic without spawning real uvicorn/browser flows.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "ui" / "ui_e2e_automation_lane.py"


def _load_module(module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_ui_e2e_automation_lane_writes_pass_artifact(tmp_path: Path, monkeypatch) -> None:
    module = _load_module("ui_e2e_automation_lane_pass")
    monkeypatch.chdir(tmp_path)
    local_dir = tmp_path / ".local"
    local_dir.mkdir(parents=True, exist_ok=True)
    (local_dir / "ui-smoke-runtime-snapshots.json").write_text(
        json.dumps({"schema_version": "1.0"}) + "\n",
        encoding="utf-8",
    )

    def _fake_run(*_args, **_kwargs):
        return subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="[PASS] UI build\n[PASS] API health\n[PASS] End-to-end smoke flow\n",
            stderr="",
        )

    monkeypatch.setattr(module, "_repo_root", lambda: tmp_path)
    monkeypatch.setattr(module.subprocess, "run", _fake_run)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ui_e2e_automation_lane.py",
            "--out",
            ".local/ui-e2e-smoke.json",
            "--log-out",
            ".local/ui-e2e-smoke.log",
        ],
    )
    assert module.main() == 0

    payload = json.loads((local_dir / "ui-e2e-smoke.json").read_text(encoding="utf-8"))
    assert payload["status"] == "pass"
    assert payload["stages_passed_total"] == 3
    assert payload["stages_failed_total"] == 0
    assert payload["runtime_snapshots_available"] is True


def test_ui_e2e_automation_lane_writes_fail_artifact(tmp_path: Path, monkeypatch) -> None:
    module = _load_module("ui_e2e_automation_lane_fail")
    monkeypatch.chdir(tmp_path)
    local_dir = tmp_path / ".local"
    local_dir.mkdir(parents=True, exist_ok=True)

    def _fake_run(*_args, **_kwargs):
        return subprocess.CompletedProcess(
            args=[],
            returncode=2,
            stdout="[PASS] UI build\n[FAIL] End-to-end smoke flow\n",
            stderr="runtime failure",
        )

    monkeypatch.setattr(module, "_repo_root", lambda: tmp_path)
    monkeypatch.setattr(module.subprocess, "run", _fake_run)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ui_e2e_automation_lane.py",
            "--out",
            ".local/ui-e2e-smoke.json",
            "--log-out",
            ".local/ui-e2e-smoke.log",
        ],
    )
    assert module.main() == 2

    payload = json.loads((local_dir / "ui-e2e-smoke.json").read_text(encoding="utf-8"))
    assert payload["status"] == "fail"
    assert payload["stages_passed_total"] == 1
    assert payload["stages_failed_total"] == 1
    assert payload["runtime_snapshots_available"] is False

