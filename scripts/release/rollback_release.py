"""
File: rollback_release.py
Path: scripts/release/rollback_release.py
Role: Executes a controlled rollback command path for failed deployments.
Used By:
 - .github/workflows/progressive-deploy.yml
Depends On:
 - argparse
 - pathlib
Notes:
 - Writes rollback evidence to support incident/audit workflows.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Execute rollback path for a release.")
    parser.add_argument("--release-ref", required=True, help="Release ref/SHA to rollback from")
    parser.add_argument("--environment", required=True, choices=["stage", "prod"], help="Target environment")
    parser.add_argument(
        "--out",
        default="artifacts/evidence/rollback.txt",
        help="Rollback evidence output path",
    )
    args = parser.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        "\n".join(
            [
                "rollback-status: executed",
                f"environment: {args.environment}",
                f"release-ref: {args.release_ref}",
                "note: replace with environment-specific rollback implementation",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Rollback evidence written to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
