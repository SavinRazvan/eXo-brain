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


def _parse_markdown(content: str, source_path: str) -> dict[str, Any]:
    lines = content.splitlines()
    idx = 0
    started_at = ""
    ended_at = ""
    context: dict[str, str] = {}
    required_links: list[dict[str, Any]] = []
    gates: list[dict[str, Any]] = []
    overall_result = "FAIL"

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
                gates.append(
                    {
                        "name": parsed_gate.group(1),
                        "status": parsed_gate.group(2).lower(),
                        "ok": parsed_gate.group(2) == "PASS",
                    }
                )
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
