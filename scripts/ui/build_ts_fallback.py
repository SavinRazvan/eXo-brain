"""
File: build_ts_fallback.py
Path: scripts/ui/build_ts_fallback.py
Role: Fallback UI build step that converts browser-safe .ts modules into .js files.
Used By:
 - scripts/ui/build.sh
Depends On:
 - pathlib
 - argparse
Notes:
 - This fallback assumes source .ts files are authored as TypeScript-compatible JavaScript.
 - It is intended for environments that do not have Node/npm installed.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fallback transpiler: copy .ts modules to .js")
    parser.add_argument("--src", required=True, help="Source directory (ui/src)")
    parser.add_argument("--dist", required=True, help="Destination directory (ui/dist)")
    return parser.parse_args()


def _copy_ts_to_js(src: Path, dist: Path) -> int:
    copied = 0
    for ts_file in src.rglob("*.ts"):
        if ts_file.name == "types.ts":
            # Type-only module; not needed by runtime fallback output.
            continue
        rel = ts_file.relative_to(src)
        out = dist / rel.with_suffix(".js")
        out.parent.mkdir(parents=True, exist_ok=True)
        text = ts_file.read_text(encoding="utf-8")
        out.write_text(text, encoding="utf-8")
        copied += 1
    return copied


def _copy_static_assets(src: Path, dist: Path) -> int:
    copied = 0
    for rel in ("index.html", "styles.css"):
        src_file = src / rel
        if not src_file.exists():
            continue
        out = dist / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(src_file.read_text(encoding="utf-8"), encoding="utf-8")
        copied += 1
    return copied


def main() -> int:
    args = _parse_args()
    src = Path(args.src)
    dist = Path(args.dist)
    if not src.exists():
        raise FileNotFoundError(f"Source directory does not exist: {src}")
    dist.mkdir(parents=True, exist_ok=True)
    copied_modules = _copy_ts_to_js(src, dist)
    copied_assets = _copy_static_assets(src, dist)
    print(f"Copied {copied_modules} module(s) and {copied_assets} static asset(s) from {src} to {dist}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
