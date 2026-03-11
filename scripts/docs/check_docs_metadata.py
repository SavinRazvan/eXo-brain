"""
File: check_docs_metadata.py
Path: scripts/docs/check_docs_metadata.py
Role: Optional docs lint utility for module-doc metadata and index existence checks.
Used By:
 - Manual maintainer workflow
 - Optional CI docs lint lane
Depends On:
 - docs/modules/
 - docs/README.md
 - docs/plans/README.md
 - docs/operations/README.md
Notes:
 - Intended as a lightweight non-blocking check unless explicitly promoted to required CI gate.
"""

from __future__ import annotations

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_DOCS = [
    REPO_ROOT / "docs/modules/core.md",
    REPO_ROOT / "docs/modules/runtime.md",
    REPO_ROOT / "docs/modules/tools.md",
    REPO_ROOT / "docs/modules/policies.md",
    REPO_ROOT / "docs/modules/api.md",
    REPO_ROOT / "docs/modules/tenancy.md",
]
INDEX_DOCS = [
    REPO_ROOT / "docs/README.md",
    REPO_ROOT / "docs/plans/README.md",
    REPO_ROOT / "docs/operations/README.md",
    REPO_ROOT / "docs/modules/README.md",
]
REQUIRED_MODULE_MARKERS = [
    "## Metadata",
    "## Primary Code Paths",
    "## Primary Tests",
    "## Contract Boundaries",
    "## Breaking-Change Policy",
]


def _check_exists(path: Path, errors: list[str]) -> None:
    if not path.exists():
        errors.append(f"Missing required documentation file: {path.relative_to(REPO_ROOT)}")


def _check_markers(path: Path, errors: list[str]) -> None:
    text = path.read_text(encoding="utf-8")
    for marker in REQUIRED_MODULE_MARKERS:
        if marker not in text:
            errors.append(
                f"Missing marker '{marker}' in {path.relative_to(REPO_ROOT)}"
            )


def main() -> int:
    errors: list[str] = []

    for file_path in INDEX_DOCS + MODULE_DOCS:
        _check_exists(file_path, errors)

    for module_doc in MODULE_DOCS:
        if module_doc.exists():
            _check_markers(module_doc, errors)

    if errors:
        print("Documentation metadata check: FAIL")
        for item in errors:
            print(f"- {item}")
        return 1

    print("Documentation metadata check: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
