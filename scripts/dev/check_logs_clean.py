#!/usr/bin/env python3
"""
File: check_logs_clean.py
Path: scripts/dev/check_logs_clean.py
Role: Fail when repository-level logs contain generated artifacts.
Used By:
 - local and CI validation workflows
Depends On:
 - pathlib
 - sys
Notes:
 - Keeps tracked placeholders only (for example `.gitkeep`) in `logs/`.
"""

from __future__ import annotations

from pathlib import Path
import sys


def main() -> int:
    """Return non-zero when repository `logs/` has generated files."""
    logs_dir = Path.cwd() / "logs"
    if not logs_dir.exists():
        return 0

    allowed = {".gitkeep"}
    artifacts = [p for p in logs_dir.iterdir() if p.is_file() and p.name not in allowed]

    if artifacts:
        print("Repository logs directory contains generated artifacts:")
        for artifact in sorted(artifacts):
            print(f"- {artifact}")
        print("Tests and tooling must write logs only to temporary or owned output paths.")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
