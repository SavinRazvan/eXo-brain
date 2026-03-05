"""
File: parse_rc_signoff.py
Path: scripts/release/parse_rc_signoff.py
Role: Parses RC signoff markdown evidence into normalized JSON.
Used By:
 - dashboards and alert pipelines
 - release operators
Depends On:
 - argparse
 - json
 - pathlib
 - re
Notes:
 - Accepts the markdown format produced by scripts/release/rc_signoff.py.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Any


_LINE_RE = re.compile(r"^- ([^:]+): `(.*)`$")
_EVIDENCE_RE = re.compile(r"^- \[(OK|MISSING)\] `(.*)`$")
_GATE_RE = re.compile(r"^### ([^:]+): (PASS|FAIL)$")
_OVERALL_RE = re.compile(r"^- Result: `(PASS|FAIL)`$")
_GATE_COMMAND_RE = re.compile(r"^- Command: `(.*)`$")
_GATE_EXIT_RE = re.compile(r"^- Exit Code: `(-?\d+)`$")
_GATE_DURATION_RE = re.compile(r"^- Duration Ms: `(\d+)`$")
_BOOL_RE = re.compile(r"^- (Enabled|Required): `(true|false)`$")
_GOV_BOOL_RE = re.compile(r"^- (Enabled|Advisory Only|Metrics Available): `(true|false)`$")
_MODE_RE = re.compile(r"^- Mode: `(advisory|required)`$")
_RESULT_RE = re.compile(r"^- Result: `(PASS|FAIL)`$")
_META_PATH_RE = re.compile(r"^- Meta Path: `(.*)`$")
_GOV_METRICS_PATH_RE = re.compile(r"^- Metrics Path: `(.*)`$")
_GOV_FLOAT_RE = re.compile(
    r"^- (Cost Utilization Threshold|Rejection Rate Threshold|Cost Utilization Ratio|Rejection Rate): `([^`]*)`$"
)
_GOV_ALERT_COUNT_RE = re.compile(r"^- Alert Count: `(\d+)`$")
_GOV_ALERTS_RE = re.compile(r"^- Alerts: `(.*)`$")
_GOV_RESULT_RE = re.compile(r"^- Result: `(PASS|ALERT|UNAVAILABLE)`$")


def _parse_markdown(content: str, source_path: str) -> dict[str, Any]:
    lines = content.splitlines()
    idx = 0
    started_at = ""
    ended_at = ""
    context: dict[str, str] = {}
    required_links: list[dict[str, Any]] = []
    gates: list[dict[str, Any]] = []
    overall_result = "FAIL"
    data_safety: dict[str, Any] = {
        "enabled": False,
        "required": False,
        "mode": "advisory",
        "command": "",
        "exit_code": None,
        "duration_ms": None,
        "result": "",
        "ok": None,
        "meta_path": "",
    }
    governance_alerts: dict[str, Any] = {
        "enabled": False,
        "advisory_only": True,
        "metrics_path": "",
        "metrics_available": False,
        "cost_utilization_threshold": None,
        "rejection_rate_threshold": None,
        "cost_utilization_ratio": None,
        "rejection_rate": None,
        "alert_count": 0,
        "alerts": [],
        "result": "UNAVAILABLE",
    }

    while idx < len(lines):
        line = lines[idx].strip()

        if line.startswith("- Started:"):
            match = _LINE_RE.match(line)
            if match:
                started_at = match.group(2)
        elif line.startswith("- Ended:"):
            match = _LINE_RE.match(line)
            if match:
                ended_at = match.group(2)
        elif line == "## Execution Context":
            idx += 1
            while idx < len(lines):
                maybe = lines[idx].strip()
                parsed = _LINE_RE.match(maybe)
                if not parsed:
                    break
                key = parsed.group(1).strip().lower().replace(" ", "_")
                context[key] = parsed.group(2)
                idx += 1
            continue
        elif line == "## Required Evidence Links":
            idx += 1
            while idx < len(lines):
                maybe = lines[idx].strip()
                parsed = _EVIDENCE_RE.match(maybe)
                if not parsed:
                    break
                status = parsed.group(1)
                required_links.append(
                    {
                        "path": parsed.group(2),
                        "status": "ok" if status == "OK" else "missing",
                        "ok": status == "OK",
                    }
                )
                idx += 1
            continue
        elif line.startswith("### "):
            parsed_gate = _GATE_RE.match(line)
            if parsed_gate:
                gate_record: dict[str, Any] = {
                    "name": parsed_gate.group(1),
                    "status": parsed_gate.group(2).lower(),
                    "ok": parsed_gate.group(2) == "PASS",
                    "command": "",
                    "exit_code": None,
                    "duration_ms": None,
                }
                cursor = idx + 1
                while cursor < len(lines):
                    maybe = lines[cursor].strip()
                    if maybe.startswith("### ") or maybe == "## Overall":
                        break
                    command_match = _GATE_COMMAND_RE.match(maybe)
                    if command_match:
                        gate_record["command"] = command_match.group(1)
                    exit_match = _GATE_EXIT_RE.match(maybe)
                    if exit_match:
                        gate_record["exit_code"] = int(exit_match.group(1))
                    duration_match = _GATE_DURATION_RE.match(maybe)
                    if duration_match:
                        gate_record["duration_ms"] = int(duration_match.group(1))
                    cursor += 1
                gates.append(
                    gate_record
                )
        elif line == "## Local Data Safety":
            cursor = idx + 1
            while cursor < len(lines):
                maybe = lines[cursor].strip()
                if maybe.startswith("## "):
                    break
                bool_match = _BOOL_RE.match(maybe)
                if bool_match:
                    key = bool_match.group(1).strip().lower()
                    data_safety[key] = bool_match.group(2) == "true"
                mode_match = _MODE_RE.match(maybe)
                if mode_match:
                    data_safety["mode"] = mode_match.group(1)
                command_match = _GATE_COMMAND_RE.match(maybe)
                if command_match:
                    data_safety["command"] = command_match.group(1)
                exit_match = _GATE_EXIT_RE.match(maybe)
                if exit_match:
                    data_safety["exit_code"] = int(exit_match.group(1))
                duration_match = _GATE_DURATION_RE.match(maybe)
                if duration_match:
                    data_safety["duration_ms"] = int(duration_match.group(1))
                result_match = _RESULT_RE.match(maybe)
                if result_match:
                    data_safety["result"] = result_match.group(1)
                    data_safety["ok"] = result_match.group(1) == "PASS"
                meta_match = _META_PATH_RE.match(maybe)
                if meta_match:
                    data_safety["meta_path"] = meta_match.group(1)
                cursor += 1
            idx = cursor
            continue
        elif line == "## Governance Alerts":
            cursor = idx + 1
            while cursor < len(lines):
                maybe = lines[cursor].strip()
                if maybe.startswith("## "):
                    break
                bool_match = _GOV_BOOL_RE.match(maybe)
                if bool_match:
                    key = (
                        bool_match.group(1)
                        .strip()
                        .lower()
                        .replace(" ", "_")
                    )
                    governance_alerts[key] = bool_match.group(2) == "true"
                metrics_path_match = _GOV_METRICS_PATH_RE.match(maybe)
                if metrics_path_match:
                    governance_alerts["metrics_path"] = metrics_path_match.group(1)
                float_match = _GOV_FLOAT_RE.match(maybe)
                if float_match:
                    key = (
                        float_match.group(1)
                        .strip()
                        .lower()
                        .replace(" ", "_")
                    )
                    value = float_match.group(2).strip()
                    governance_alerts[key] = None if value == "n/a" else float(value)
                count_match = _GOV_ALERT_COUNT_RE.match(maybe)
                if count_match:
                    governance_alerts["alert_count"] = int(count_match.group(1))
                alerts_match = _GOV_ALERTS_RE.match(maybe)
                if alerts_match:
                    raw_alerts = alerts_match.group(1).strip()
                    governance_alerts["alerts"] = [] if raw_alerts in {"", "none"} else [
                        item.strip() for item in raw_alerts.split(",") if item.strip()
                    ]
                result_match = _GOV_RESULT_RE.match(maybe)
                if result_match:
                    governance_alerts["result"] = result_match.group(1)
                cursor += 1
            idx = cursor
            continue
        elif line == "## Overall":
            idx += 1
            while idx < len(lines):
                maybe = lines[idx].strip()
                parsed = _OVERALL_RE.match(maybe)
                if parsed:
                    overall_result = parsed.group(1)
                    break
                idx += 1
            continue
        idx += 1

    missing_links = [entry["path"] for entry in required_links if not entry["ok"]]
    failed_gates = [entry["name"] for entry in gates if not entry["ok"]]
    passed = overall_result == "PASS"

    return {
        "schema_version": "1.0",
        "source_path": source_path,
        "started_at": started_at,
        "ended_at": ended_at,
        "context": context,
        "required_evidence_links": required_links,
        "gates": gates,
        "data_safety": data_safety,
        "governance_alerts": governance_alerts,
        "overall": {
            "result": overall_result,
            "passed": passed,
            "missing_evidence_links": missing_links,
            "failed_gates": failed_gates,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Parse RC signoff markdown into normalized JSON.")
    parser.add_argument(
        "--in",
        dest="input_path",
        default=".local/rc-signoff.md",
        help="Path to RC signoff markdown evidence.",
    )
    parser.add_argument(
        "--out",
        dest="output_path",
        default=".local/rc-signoff.json",
        help="Path to write normalized JSON summary.",
    )
    args = parser.parse_args()

    input_path = Path(args.input_path)
    if not input_path.exists():
        print(f"Input file not found: {input_path}")
        return 1

    content = input_path.read_text(encoding="utf-8")
    payload = _parse_markdown(content, str(input_path))

    output_path = Path(args.output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Parsed RC signoff JSON written to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
