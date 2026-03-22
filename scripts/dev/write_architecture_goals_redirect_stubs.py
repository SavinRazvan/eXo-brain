"""
File: write_architecture_goals_redirect_stubs.py
Path: scripts/dev/write_architecture_goals_redirect_stubs.py
Role: Writes thin redirect stubs under architecture-goals/ pointing at docs/strategy canonical files.
Used By:
 - Maintainers (manual): `python scripts/dev/write_architecture_goals_redirect_stubs.py`
Depends On:
 - pathlib
Notes:
 - Preserves historical paths for bookmarks while making docs/strategy the durable home.
"""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
AG = REPO / "architecture-goals"

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


def main() -> int:
    AG.mkdir(parents=True, exist_ok=True)
    for old, new in FILE_MAP.items():
        body = f"""<!--
File: {old}
Path: architecture-goals/{old}
Role: Redirect stub; canonical strategy content lives in docs/strategy/.
Used By:
 - Historical links and bookmarks
Depends On:
 - docs/strategy/{new}
Notes:
 - Edit docs/strategy/{new} instead of this file.
-->

# Moved

Canonical document: **[docs/strategy/{new}](../docs/strategy/{new})**.
"""
        (AG / old).write_text(body, encoding="utf-8")
    print(f"Wrote {len(FILE_MAP)} stubs under {AG}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
