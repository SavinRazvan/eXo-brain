"""
File: verify_provenance.py
Path: scripts/release/verify_provenance.py
Role: Produces basic release provenance metadata for evidence bundling.
Used By:
 - .github/workflows/release-candidate.yml
Depends On:
 - json
 - os
 - pathlib
Notes:
 - Placeholder provenance step until artifact signing is integrated.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Write minimal provenance metadata.")
    parser.add_argument(
        "--out",
        default="artifacts/evidence/provenance.json",
        help="Output JSON file path",
    )
    args = parser.parse_args()

    payload = {
        "source": {
            "sha": os.getenv("GITHUB_SHA", ""),
            "ref": os.getenv("GITHUB_REF", ""),
            "repository": os.getenv("GITHUB_REPOSITORY", ""),
        },
        "builder": {
            "workflow": os.getenv("GITHUB_WORKFLOW", ""),
            "run_id": os.getenv("GITHUB_RUN_ID", ""),
            "actor": os.getenv("GITHUB_ACTOR", ""),
        },
        "status": "provenance-recorded",
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote provenance metadata to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
