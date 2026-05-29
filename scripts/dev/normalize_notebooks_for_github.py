"""
File: normalize_notebooks_for_github.py
Path: scripts/dev/normalize_notebooks_for_github.py
Role: Normalize committed .ipynb files for GitHub in-browser preview without regenerating content.
Used By:
 - Maintainers before push when GitHub shows nbformat/nbconvert render errors
Depends On:
 - notebooks/notebook_common.py
Notes:
 - Does not run build_tutorials/build_checks; only adjusts metadata and nbformat version.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
NB_DIR = REPO_ROOT / "notebooks"

if str(NB_DIR) not in sys.path:
    sys.path.insert(0, str(NB_DIR))

import nbformat as nbf

from notebook_common import write_github_compatible_notebook


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize notebook JSON for GitHub preview.")
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="Notebook paths (default: notebooks/*.ipynb)",
    )
    args = parser.parse_args()
    paths = args.paths or sorted(NB_DIR.glob("*.ipynb"))

    for path in paths:
        nb = nbf.read(path.open(encoding="utf-8"), as_version=4)
        write_github_compatible_notebook(nb, path)
        print(f"normalized: {path.relative_to(REPO_ROOT)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
