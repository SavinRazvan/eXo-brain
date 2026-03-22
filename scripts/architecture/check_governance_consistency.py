"""
File: check_governance_consistency.py
Path: scripts/architecture/check_governance_consistency.py
Role: Detect governance drift across active rules, skills, merge checks, and CI wiring.
Used By:
 - .github/workflows/architecture-fitness.yml
Depends On:
 - pathlib
Notes:
 - Fails fast on stale references to removed governance research documents.
 - Enforces parity checks for merge prechecks and canonical skill ownership shims.
"""

from __future__ import annotations

from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]
BANNED_REFERENCE = ".cursor/research-for-refactor/"

GOVERNANCE_SCAN_TARGETS = (
    "scripts/pr/merge.py",
    ".github/workflows/architecture-fitness.yml",
)


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"unable to read {path}: {exc}") from exc


def _collect_banned_reference_violations() -> list[str]:
    violations: list[str] = []
    for target in GOVERNANCE_SCAN_TARGETS:
        if _is_gitignored(target):
            continue
        absolute = ROOT / target
        if absolute.is_file():
            text = _read_text(absolute)
            if BANNED_REFERENCE in text:
                rel = absolute.relative_to(ROOT).as_posix()
                violations.append(f"{rel}: contains stale reference '{BANNED_REFERENCE}'")
            continue

        if absolute.is_dir():
            for path in absolute.rglob("*"):
                if not path.is_file():
                    continue
                text = _read_text(path)
                if BANNED_REFERENCE in text:
                    rel = path.relative_to(ROOT).as_posix()
                    violations.append(f"{rel}: contains stale reference '{BANNED_REFERENCE}'")
            continue

        # Optional governance targets may be absent by repo policy.
        continue
    return violations


def _contains_required(path: str, required_fragments: tuple[str, ...]) -> list[str]:
    violations: list[str] = []
    if _is_gitignored(path):
        return violations
    absolute = ROOT / path
    if not absolute.exists():
        return [f"{path}: required file is missing"]
    text = _read_text(absolute)
    for fragment in required_fragments:
        if fragment not in text:
            violations.append(f"{path}: missing required fragment '{fragment}'")
    return violations


def _collect_contract_parity_violations() -> list[str]:
    violations: list[str] = []
    violations.extend(
        _contains_required(
            "scripts/pr/merge.py",
            (
                ".local/workflow-artifacts/alignment/alignment-audit.md",
                ".local/workflow-artifacts/alignment/alignment-todos.md",
            ),
        )
    )
    violations.extend(
        _contains_required(
            ".github/workflows/architecture-fitness.yml",
            ("python scripts/architecture/check_governance_consistency.py",),
        )
    )
    return violations


def _is_gitignored(path: str) -> bool:
    try:
        result = subprocess.run(
            ["git", "check-ignore", "--no-index", path],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return False
    return result.returncode == 0


def main() -> int:
    violations = _collect_banned_reference_violations()
    violations.extend(_collect_contract_parity_violations())
    if violations:
        print("Governance consistency check failed:")
        for violation in violations:
            print(f" - {violation}")
        return 1

    print("Governance consistency check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
