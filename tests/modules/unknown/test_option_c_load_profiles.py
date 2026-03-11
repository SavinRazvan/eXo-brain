"""
File: test_option_c_load_profiles.py
Path: tests/modules/unknown/test_option_c_load_profiles.py
Role: Validate Option C load profile script enforcement output path.
Used By:
 - CI test suite
Depends On:
 - scripts/perf/option_c_load_profiles.py
Notes:
 - Ensures threshold-enforcement mode returns deterministic pass/fail codes.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "perf" / "option_c_load_profiles.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("option_c_load_profiles_script", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["option_c_load_profiles_script"] = module
    spec.loader.exec_module(module)
    return module


def test_option_c_load_profiles_enforce_writes_json(tmp_path: Path, monkeypatch) -> None:
    module = _load_module()
    thresholds = tmp_path / "thresholds.json"
    thresholds.write_text(
        json.dumps(
            {
                "max_p95_wait_ms": 1000.0,
                "max_rejection_ratio": 0.5,
                "max_starvation_tenants": 0,
            }
        ),
        encoding="utf-8",
    )
    out_json = tmp_path / "out.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "option_c_load_profiles.py",
            "--enforce",
            "--thresholds-json",
            str(thresholds),
            "--json-out",
            str(out_json),
            "--requests-per-tenant",
            "20",
        ],
    )
    assert module.main() == 0
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert len(payload["profiles"]) == 3
