"""
File: migrate_strategy_docs.py
Path: scripts/dev/migrate_strategy_docs.py
Role: One-shot helper to copy architecture-goals markdown into docs/strategy with kebab-case names and updated cross-links.
Used By:
 - Maintainers running enterprise docs migration (manual invocation).
Depends On:
 - pathlib
Notes:
 - Run from repo root: `python scripts/dev/migrate_strategy_docs.py`
 - Overwrites docs/strategy/*.md targets. Does not modify architecture-goals (stubs are maintained separately).
"""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SRC = REPO / "architecture-goals"
DST = REPO / "docs" / "strategy"

# architecture-goals/FILENAME -> docs/strategy/target
FILE_MAP: dict[str, str] = {
    "README.md": "README.md",
    "GOAL.md": "goal.md",
    "CORE.md": "core.md",
    "NEXT_DIRECTIONS.md": "next-directions.md",
    "ADAPTER_STRATEGY.md": "adapter-strategy.md",
    "MONETIZATION_STRATEGY.md": "monetization-strategy.md",
    "ENTITLEMENT_MATRIX.md": "entitlement-matrix.md",
    "COMPLIANCE_PROFILE_MATRIX.md": "compliance-profile-matrix.md",
    "DEPLOYMENT_MODELS.md": "deployment-models.md",
    "INTERFACE_STRATEGY.md": "interface-strategy.md",
    "TRACEABILITY_MATRIX.md": "traceability-matrix.md",
    "EXECUTION_BOARD_12_GAPS.md": "execution-board-12-gaps.md",
}


def _build_link_replacements() -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for old_name, new_name in FILE_MAP.items():
        pairs.append((f"architecture-goals/{old_name}", new_name))
        pairs.append((f"`architecture-goals/{old_name}`", f"`{new_name}`"))
    # Longest-first to avoid partial replacements
    pairs.sort(key=lambda x: len(x[0]), reverse=True)
    return pairs


def main() -> int:
    DST.mkdir(parents=True, exist_ok=True)
    repls = _build_link_replacements()
    for old_name, new_name in FILE_MAP.items():
        src = SRC / old_name
        if not src.exists():
            raise SystemExit(f"missing source: {src}")
        raw = src.read_text(encoding="utf-8")
        for old_link, new_link in repls:
            raw = raw.replace(old_link, new_link)
        raw = raw.replace(
            f"Path: architecture-goals/{old_name}",
            f"Path: docs/strategy/{new_name}",
        )
        (DST / new_name).write_text(raw, encoding="utf-8")
    print(f"Wrote {len(FILE_MAP)} files under {DST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
