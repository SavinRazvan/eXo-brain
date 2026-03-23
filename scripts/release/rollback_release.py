"""
File: rollback_release.py
Path: scripts/release/rollback_release.py
Role: Executes a controlled rollback command path for failed deployments.
Used By:
 - .github/workflows/progressive-deploy.yml
Depends On:
 - argparse
 - json
 - pathlib
Notes:
 - Writes structured rollback evidence (JSON + human-readable) for incident/audit workflows.
 - Integrators should replace the stub hook with environment-specific automation.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen


def main() -> int:
    parser = argparse.ArgumentParser(description="Execute rollback path for a release.")
    parser.add_argument("--release-ref", required=True, help="Release ref/SHA to rollback from")
    parser.add_argument("--environment", required=True, choices=["stage", "prod"], help="Target environment")
    parser.add_argument(
        "--out",
        default="artifacts/evidence/rollback.txt",
        help="Rollback evidence output path (human-readable)",
    )
    parser.add_argument(
        "--json-out",
        default="artifacts/evidence/rollback.json",
        help="Structured rollback evidence path",
    )
    parser.add_argument(
        "--readiness-url",
        default="",
        help="Optional URL to GET after rollback for verification (e.g. https://api.example/ready)",
    )
    args = parser.parse_args()

    executed_at = datetime.now(timezone.utc).isoformat()
    readiness_status: str | None = None
    if str(args.readiness_url or "").strip():
        url = str(args.readiness_url).strip()
        try:
            req = Request(url, method="GET", headers={"User-Agent": "exo-brain-rollback/1.0"})
            with urlopen(req, timeout=15) as resp:  # noqa: S310 — explicit operator-supplied URL
                readiness_status = f"http_{resp.status}"
        except URLError as exc:
            readiness_status = f"error:{exc}"

    record = {
        "rollback_status": "stub_executed",
        "environment": args.environment,
        "release_ref": args.release_ref,
        "executed_at_utc": executed_at,
        "readiness_probe": readiness_status,
        "note": "Replace rollback_status stub with environment-specific automation when available.",
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        "\n".join(
            [
                "rollback-status: executed",
                f"environment: {args.environment}",
                f"release-ref: {args.release_ref}",
                f"executed_at_utc: {executed_at}",
                f"readiness_probe: {readiness_status or 'not_requested'}",
                "note: see rollback.json for structured evidence",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    json_path = Path(args.json_out)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")

    print(f"Rollback evidence written to {out_path} and {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
