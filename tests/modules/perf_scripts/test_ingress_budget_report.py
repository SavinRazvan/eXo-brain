"""
File: test_ingress_budget_report.py
Path: tests/modules/perf_scripts/test_ingress_budget_report.py
Role: Validates ingress budget report script profile-aware output and threshold enforcement.
Used By:
 - CI test suite
Depends On:
 - scripts/perf/ingress_budget_report.py
Notes:
 - Keeps profile-specific ingress SLO reporting deterministic.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "perf" / "ingress_budget_report.py"


def _load_module(module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_ingress_budget_report_enforce_writes_profile_json(tmp_path: Path, monkeypatch) -> None:
    module = _load_module("ingress_budget_report_script")
    thresholds = tmp_path / "thresholds.json"
    thresholds.write_text(
        json.dumps(
            {
                "max_p95_ingress_latency_ms": 500.0,
                "max_timeout_rate": 0.5,
                "profiles": {
                    "baseline": {"max_p95_ingress_latency_ms": 500.0, "max_timeout_rate": 0.5},
                    "strict": {"max_p95_ingress_latency_ms": 500.0, "max_timeout_rate": 0.5},
                    "hardened": {"max_p95_ingress_latency_ms": 500.0, "max_timeout_rate": 0.5},
                },
            }
        ),
        encoding="utf-8",
    )
    out_json = tmp_path / "ingress_budget_report.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ingress_budget_report.py",
            "--enforce",
            "--thresholds-json",
            str(thresholds),
            "--json-out",
            str(out_json),
            "--samples",
            "2",
            "--timeout-samples",
            "1",
            "--timeout-ms",
            "15",
        ],
    )
    assert module.main() == 0
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    profile_names = [row.get("profile") for row in payload["profiles"]]
    assert profile_names == ["baseline", "strict", "hardened"]


def test_ingress_budget_report_fails_when_profile_threshold_breached(tmp_path: Path, monkeypatch) -> None:
    module = _load_module("ingress_budget_report_script_fail")
    thresholds = tmp_path / "thresholds.json"
    thresholds.write_text(
        json.dumps(
            {
                "max_p95_ingress_latency_ms": 500.0,
                "max_timeout_rate": 0.5,
                "profiles": {
                    "strict": {"max_p95_ingress_latency_ms": 500.0, "max_timeout_rate": 0.0},
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ingress_budget_report.py",
            "--enforce",
            "--thresholds-json",
            str(thresholds),
            "--samples",
            "1",
            "--timeout-samples",
            "1",
            "--timeout-ms",
            "10",
        ],
    )
    assert module.main() == 1
