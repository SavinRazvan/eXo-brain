"""
File: generate_coverage_index.py
Path: scripts/dev/generate_coverage_index.py
Role: Build a markdown coverage index from coverage.py JSON output.
Used By:
 - Local development workflows
 - CI coverage evidence steps
Depends On:
 - coverage.py JSON report format
 - .local/index-and-planning/current/coverage-index.md
Notes:
 - This script is read-only for source/tests; it only writes the index artifact.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class FileCoverage:
    path: str
    module: str
    statements: int
    covered: int
    missing: int
    percent: float


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a markdown coverage index from coverage JSON output."
    )
    parser.add_argument(
        "--coverage-json",
        default=".local/generated-data/coverage/coverage.json",
        help="Path to coverage JSON file (default: .local/generated-data/coverage/coverage.json).",
    )
    parser.add_argument(
        "--output",
        default=".local/index-and-planning/current/coverage-index.md",
        help="Markdown output path (default: .local/index-and-planning/current/coverage-index.md).",
    )
    parser.add_argument(
        "--low-threshold",
        type=float,
        default=90.0,
        help="Threshold used for low-coverage reporting (default: 90.0).",
    )
    parser.add_argument(
        "--top-missing",
        type=int,
        default=20,
        help="Max number of top missing files to list (default: 20).",
    )
    return parser.parse_args()


def _load_coverage_rows(payload: dict[str, object]) -> list[FileCoverage]:
    files = payload.get("files", {})
    if not isinstance(files, dict):
        raise ValueError("Invalid coverage JSON: missing files map.")
    rows: list[FileCoverage] = []
    for path, meta in files.items():
        if not isinstance(path, str) or not path.startswith("src/"):
            continue
        if not isinstance(meta, dict):
            continue
        summary = meta.get("summary", {})
        if not isinstance(summary, dict):
            continue
        statements = int(summary.get("num_statements", 0))
        covered = int(summary.get("covered_lines", 0))
        missing = int(summary.get("missing_lines", 0))
        percent = float(summary.get("percent_covered", 0.0))
        parts = path.split("/")
        module = parts[1] if len(parts) > 1 else "unknown"
        rows.append(
            FileCoverage(
                path=path,
                module=module,
                statements=statements,
                covered=covered,
                missing=missing,
                percent=percent,
            )
        )
    return rows


def _module_summary(rows: list[FileCoverage]) -> list[tuple[str, int, int, int, float]]:
    module_map: dict[str, dict[str, int]] = {}
    for row in rows:
        stats = module_map.setdefault(
            row.module,
            {"files": 0, "statements": 0, "covered": 0, "missing": 0},
        )
        stats["files"] += 1
        stats["statements"] += row.statements
        stats["covered"] += row.covered
        stats["missing"] += row.missing
    data: list[tuple[str, int, int, int, float]] = []
    for module, stats in module_map.items():
        statements = stats["statements"]
        percent = (stats["covered"] / statements * 100.0) if statements else 100.0
        data.append((module, stats["files"], statements, stats["missing"], percent))
    return sorted(data, key=lambda entry: (entry[4], entry[0]))


def _render(
    *,
    rows: list[FileCoverage],
    module_rows: list[tuple[str, int, int, int, float]],
    totals: dict[str, object],
    low_threshold: float,
    top_missing: int,
) -> str:
    generated_at = datetime.now(timezone.utc).isoformat()
    total_statements = int(totals.get("num_statements", 0))
    total_covered = int(totals.get("covered_lines", 0))
    total_missing = int(totals.get("missing_lines", 0))
    total_percent = float(totals.get("percent_covered", 0.0))
    low_rows = [row for row in rows if row.percent < low_threshold]
    low_rows.sort(key=lambda row: (row.percent, -row.missing, row.path))
    top_missing_rows = sorted(rows, key=lambda row: row.missing, reverse=True)[:top_missing]

    lines: list[str] = [
        "<!--",
        "File: coverage-index.md",
        "Path: .local/index-and-planning/current/coverage-index.md",
        "Role: Generated index of source coverage status by module and file.",
        "Used By:",
        " - .local/index-and-planning/current/test-plan.md",
        " - .local/index-and-planning/current/test-index.md",
        "Depends On:",
        " - coverage.py JSON report",
        " - scripts/dev/generate_coverage_index.py",
        "Notes:",
        " - Regenerate after coverage runs to track progress toward 100%.",
        "-->",
        "",
        "# Coverage Index",
        "",
        f"- Generated at (UTC): `{generated_at}`",
        f"- Source files indexed: `{len(rows)}`",
        f"- Total statements: `{total_statements}`",
        f"- Covered lines: `{total_covered}`",
        f"- Missing lines: `{total_missing}`",
        f"- Total coverage: `{total_percent:.2f}%`",
        f"- Low threshold: `{low_threshold:.1f}%`",
        "",
        "## Module Coverage",
        "",
        "| Module | Files | Statements | Missing | Coverage |",
        "|---|---:|---:|---:|---:|",
    ]

    for module, files, statements, missing, percent in module_rows:
        lines.append(f"| `{module}` | {files} | {statements} | {missing} | {percent:.2f}% |")

    lines.extend(
        [
            "",
            "## Files Below Threshold",
            "",
            "| File | Statements | Missing | Coverage |",
            "|---|---:|---:|---:|",
        ]
    )
    if not low_rows:
        lines.append("| _(none)_ | 0 | 0 | 100.00% |")
    else:
        for row in low_rows:
            lines.append(
                f"| `{row.path}` | {row.statements} | {row.missing} | {row.percent:.2f}% |"
            )

    lines.extend(
        [
            "",
            f"## Top {top_missing} Files By Missing Lines",
            "",
            "| File | Missing | Statements | Coverage |",
            "|---|---:|---:|---:|",
        ]
    )
    for row in top_missing_rows:
        lines.append(f"| `{row.path}` | {row.missing} | {row.statements} | {row.percent:.2f}% |")

    return "\n".join(lines) + "\n"


def main() -> int:
    args = _parse_args()
    coverage_json_path = Path(args.coverage_json)
    if not coverage_json_path.exists():
        raise FileNotFoundError(f"Coverage JSON not found: {coverage_json_path}")
    payload = json.loads(coverage_json_path.read_text(encoding="utf-8"))
    totals = payload.get("totals", {})
    if not isinstance(totals, dict):
        raise ValueError("Invalid coverage JSON: missing totals map.")
    rows = _load_coverage_rows(payload)
    module_rows = _module_summary(rows)
    content = _render(
        rows=rows,
        module_rows=module_rows,
        totals=totals,
        low_threshold=float(args.low_threshold),
        top_missing=max(int(args.top_missing), 1),
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    print(f"Wrote coverage index to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
